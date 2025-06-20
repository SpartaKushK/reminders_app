# src/reminder_app/llm.py
from tenacity import retry, stop_after_attempt, wait_exponential
import google.generativeai as genai
from config import GOOGLE_API_KEY, TODAY
import logging
import re
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


class GeminiLLM:
    def __init__(self):
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

            # Enhanced generation config for better consistency
            self.generation_config = genai.types.GenerationConfig(
                temperature=0.3,  # Lower temperature for more consistent outputs
                top_p=0.8,
                top_k=40,
                max_output_tokens=500,
            )

        except Exception as e:
            logging.error(f"Failed to initialize Gemini API: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=30, max=120))
    def generate_reminder(self, text: str, sender: str = "Unknown", conversation_context=None):
        """Generate a reminder from a text message with enhanced prompting"""
        try:
            # Build context if available
            context_text = ""
            if conversation_context and not conversation_context.empty:
                context_text = "\n\nRecent conversation context:\n"
                for _, msg in conversation_context.head(3).iterrows():
                    sender_label = "Me" if msg['is_from_me'] else "Them"
                    context_text += f"{sender_label}: {msg['text'][:100]}...\n"

            prompt = f"""
            You are an expert AI assistant that identifies actionable tasks and reminders from text messages.

            Your job is to:
            1. Determine if the message contains ANY actionable item, task, request, or something that needs follow-up
            2. If yes, create a clear, concise reminder
            3. Extract or infer an appropriate due date/time

            Types of actionable items include:
            - Direct requests ("Can you...", "Please...")
            - Appointments/meetings ("Let's meet...", "See you at...")
            - Tasks with deadlines ("Need this by...", "Due...")
            - Events ("Don't forget...", "Remember to...")
            - Questions that need responses
            - Commitments made ("I'll...", "We should...")

            Current date/time: {TODAY} (today)
            Message from {sender}: "{text}"
            {context_text}

            RESPONSE FORMAT (must be exact):
            REMINDER: [Clear, actionable reminder text in 1-2 sentences]
            DUE: [AppleScript date format OR "missing value"]

            AppleScript date formatting rules:
            - Specific date/time: date "MM/DD/YYYY HH:MM AM/PM"
            - Date only: date "MM/DD/YYYY 12:00 PM"
            - No clear timing: missing value

            Time inference guidelines:
            - "today" = today at 6:00 PM
            - "tomorrow" = tomorrow at 12:00 PM  
            - "this week" = Friday at 5:00 PM
            - "next week" = next Friday at 12:00 PM
            - "ASAP" or "urgent" = today at 8:00 PM
            - For questions/responses = tomorrow at 10:00 AM
            - Meeting times = use exact time mentioned

            If NO actionable item is found, respond with exactly: "NO"

            Examples:
            Message: "Can you pick up milk on your way home?"
            REMINDER: Pick up milk on the way home
            DUE: date "{datetime.now().strftime('%m/%d/%Y')} 06:00 PM"

            Message: "Meeting at 3pm tomorrow"
            REMINDER: Attend meeting
            DUE: date "{(datetime.now() + timedelta(days=1)).strftime('%m/%d/%Y')} 03:00 PM"
            """

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )

            if not response or not response.text:
                logging.error("Empty response from Gemini API")
                return None

            reminder_response = response.text.strip()

            # Check if no actionable item found
            if reminder_response.upper().strip() == "NO":
                return None

            # Parse the response
            lines = [line.strip()
                     for line in reminder_response.split('\n') if line.strip()]

            if len(lines) < 2:
                logging.error(
                    f"Unexpected response format: {reminder_response}")
                return None

            reminder_line = None
            due_line = None

            for line in lines:
                if line.startswith("REMINDER:"):
                    reminder_line = line
                elif line.startswith("DUE:"):
                    due_line = line

            if not reminder_line or not due_line:
                logging.error(
                    f"Missing REMINDER or DUE line in response: {reminder_response}")
                return None

            # Extract reminder text and due date
            reminder_text = reminder_line.replace("REMINDER:", "").strip()
            if reminder_text.startswith('"') and reminder_text.endswith('"'):
                reminder_text = reminder_text[1:-1]

            due_date = due_line.replace("DUE:", "").strip()

            # Validate and clean up the reminder text
            reminder_text = self._clean_reminder_text(reminder_text)
            due_date = self._validate_due_date(due_date)

            logging.info(
                f"Generated reminder: {reminder_text[:50]}... | Due: {due_date}")

            return (reminder_text, due_date, sender)

        except Exception as e:
            logging.error(f"Error generating reminder: {e}")
            raise

    def _clean_reminder_text(self, text):
        """Clean and validate reminder text"""
        if not text or len(text.strip()) == 0:
            return "Follow up on message"

        # Remove extra quotes and clean up
        text = text.strip('"\'')

        # Ensure it starts with a capital letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        # Ensure reasonable length
        if len(text) > 200:
            text = text[:197] + "..."

        return text

    def _validate_due_date(self, due_date):
        """Validate and fix due date format"""
        if not due_date or due_date.lower().strip() == 'missing value':
            return 'missing value'

        # Clean up the due date
        due_date = due_date.strip()

        # Check if it's already in proper AppleScript format
        if due_date.startswith('date "') and due_date.endswith('"'):
            return due_date

        # If it looks like a date but missing the wrapper, add it
        date_pattern = r'\d{1,2}/\d{1,2}/\d{4}.*'
        if re.match(date_pattern, due_date):
            if not due_date.startswith('date "'):
                due_date = f'date "{due_date}"'
            return due_date

        # If we can't parse it, return missing value
        return 'missing value'

    def batch_generate_reminders(self, messages_df, batch_size=5):
        """Generate reminders for multiple messages in batches"""
        reminders = []

        for i in range(0, len(messages_df), batch_size):
            batch = messages_df.iloc[i:i+batch_size]

            for _, row in batch.iterrows():
                try:
                    sender = row.get("sender", "Unknown")
                    text = row["text"]

                    result = self.generate_reminder(text, sender)
                    if result:
                        reminders.append(result)

                except Exception as e:
                    logging.error(f"Failed to process message in batch: {e}")
                    continue

            # Brief pause between batches to respect API limits
            import time
            time.sleep(1)

        return reminders

    def analyze_message_urgency(self, text):
        """Analyze message to determine urgency level"""
        urgent_keywords = [
            'urgent', 'asap', 'emergency', 'immediately', 'right now',
            'urgent!', 'help!', 'critical', 'important!', 'deadline'
        ]

        high_priority_keywords = [
            'today', 'tonight', 'this morning', 'this afternoon',
            'need now', 'quick', 'fast', 'soon'
        ]

        text_lower = text.lower()

        for keyword in urgent_keywords:
            if keyword in text_lower:
                return 'urgent'

        for keyword in high_priority_keywords:
            if keyword in text_lower:
                return 'high'

        return 'normal'

    def extract_people_mentioned(self, text):
        """Extract people mentioned in the text for better context"""
        # Simple name extraction - could be enhanced with NLP
        people = []

        # Look for common name patterns
        name_patterns = [
            r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # First Last
            # Name before action verbs
            r'\b[A-Z][a-z]+\b(?=\s(?:said|told|asked|mentioned))',
        ]

        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            people.extend(matches)

        return list(set(people))  # Remove duplicates

    def suggest_reminder_categories(self, text):
        """Suggest categories for the reminder"""
        categories = {
            'meeting': ['meeting', 'call', 'appointment', 'conference', 'zoom'],
            'task': ['task', 'work', 'project', 'assignment', 'job'],
            'personal': ['dinner', 'lunch', 'family', 'friend', 'birthday'],
            'shopping': ['buy', 'pick up', 'get', 'purchase', 'store'],
            'travel': ['flight', 'trip', 'travel', 'vacation', 'hotel'],
            'health': ['doctor', 'appointment', 'dentist', 'medication', 'hospital'],
            'finance': ['payment', 'bill', 'bank', 'money', 'budget']
        }

        text_lower = text.lower()
        suggested = []

        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                suggested.append(category)

        return suggested if suggested else ['general']

# from tenacity import retry, stop_after_attempt, wait_exponential
# import google.generativeai as genai
# from config import GOOGLE_API_KEY, TODAY
# import logging

# # Configure logging
# logging.basicConfig(level=logging.INFO,
#                     format="%(asctime)s - %(levelname)s - %(message)s")


# class GeminiLLM:
#     def __init__(self):
#         try:
#             genai.configure(api_key=GOOGLE_API_KEY)
#             # List available models to verify
#             # for m in genai.list_models():
#             #     if 'generateContent' in m.supported_generation_methods:
#             #         logging.info(f"Found model: {m.name}")
#             self.model = genai.GenerativeModel('gemini-1.5-flash')
#         except Exception as e:
#             logging.error(f"Failed to initialize Gemini API: {e}")
#             raise

#     @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=30, max=120))
#     def generate_reminder(self, text: str, sender: str = "Unknown"):
#         try:
#             prompt = f"""
#             You are an expert task scheduler. The following message may contain an action item or task with a potential time/date.
#             If there is a task, summarize it into a short, actionable reminder (1-2 sentences max).
#             If there's a time or date mentioned for the reminder, include it in the reminder. If it's not explicit, do your best to infer a reasonable time. If that's not possible, use "missing value". If there isn't a task, just return "NO".

#             Format your response exactly as follows:
#             REMINDER: "<text>"
#             DUE: <AppleScript date format>

#             For AppleScript date formatting:
#             - If a specific date and time is mentioned, format as: date "MM/DD/YYYY HH:MM AM/PM"
#             - If only a date is mentioned, use: date "MM/DD/YYYY 12:00 AM"
#             - If no date is found, use: missing value

#             Note: Today's date is: {TODAY}. If there is context such as do something tomorrow or next week, use today's date information to create a reminder in the future in AppleScript Date formatting.

#             Message from {sender}: "{text}"
#             """
#             response = self.model.generate_content(prompt)
#             if not response or not response.text:
#                 logging.error("Empty response from Gemini API")
#                 return None

#             reminder = response.text.strip()
#             if reminder.upper() == "NO":
#                 return None

#             parts = reminder.split('\n')
#             if len(parts) != 2:
#                 logging.error("Unexpected response format from Gemini API")
#                 return None

#             reminder_text = parts[0].replace("REMINDER:", "").strip()
#             due_date = parts[1].replace("DUE:", "").strip()
#             return (reminder_text, due_date if due_date.lower() != 'missing value' else 'missing value', sender)
#         except Exception as e:
#             logging.error(f"Error generating reminder: {e}")
#             raise
