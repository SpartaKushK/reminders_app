# src/reminder_app/reminder.py
import subprocess
import logging
import re
from datetime import datetime


class ReminderManager:
    def __init__(self, default_list="Reminders"):
        self.default_list = default_list

    def create_reminder(self, reminder_data, reminder_list=None):
        """Create a reminder with improved error handling and validation"""
        try:
            if len(reminder_data) == 2:
                reminder_text, due_date = reminder_data
                source_info = ""
            else:
                reminder_text, due_date, source_info = reminder_data

            # Clean and validate reminder text
            reminder_text = self._clean_reminder_text(reminder_text)
            target_list = reminder_list or self.default_list

            # Build AppleScript command based on due date
            if due_date and due_date.strip().lower() != 'missing value':
                applescript_cmd = self._build_applescript_with_date(
                    reminder_text, due_date, target_list, source_info
                )
            else:
                applescript_cmd = self._build_applescript_no_date(
                    reminder_text, target_list, source_info
                )

            # Execute the AppleScript
            result = subprocess.run(
                ['osascript', '-e', applescript_cmd],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown AppleScript error"
                raise Exception(f"AppleScript execution failed: {error_msg}")

            logging.info(
                f"Successfully created reminder: {reminder_text[:50]}... (Due: {due_date if due_date else 'Not specified'})")
            return True

        except subprocess.TimeoutExpired:
            raise Exception("Reminder creation timed out")
        except Exception as e:
            logging.error(f"Error creating reminder: {e}")
            raise

    def _clean_reminder_text(self, text):
        """Clean reminder text for AppleScript compatibility"""
        if not text:
            return "Follow up on message"

        # Escape quotes and backslashes for AppleScript
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')

        # Remove any problematic characters
        text = re.sub(r'[^\w\s\-.,!?:;()\[\]/@#$%&*+=<>]', '', text)

        # Ensure reasonable length
        if len(text) > 200:
            text = text[:197] + "..."

        return text.strip()

    def _build_applescript_with_date(self, reminder_text, due_date, reminder_list, source_info=""):
        """Build AppleScript command with due date"""
        # Add source information to the reminder text if available
        if source_info:
            reminder_text = f"{reminder_text} (from {source_info})"

        return f'''
        tell application "Reminders"
            try
                set targetList to list "{reminder_list}"
            on error
                set targetList to default list
            end try
            
            try
                if "{due_date}" contains "date" then
                    set dueDateStr to "{due_date}"
                    set dueDateObj to run script dueDateStr
                    make new reminder at end of targetList with properties {{name:"{reminder_text}", due date:dueDateObj}}
                else
                    -- Parse custom date format
                    set dueDateObj to my parseCustomDate("{due_date}")
                    make new reminder at end of targetList with properties {{name:"{reminder_text}", due date:dueDateObj}}
                end if
            on error errorMsg
                -- Fallback: create without date if date parsing fails
                make new reminder at end of targetList with properties {{name:"{reminder_text}"}}
                log "Date parsing failed, created reminder without date: " & errorMsg
            end try
        end tell
        
        on parseCustomDate(dateStr)
            -- Custom date parsing logic for various formats
            set currentDate to current date
            
            if dateStr contains "tomorrow" then
                return currentDate + 1 * days
            else if dateStr contains "next week" then
                return currentDate + 7 * days
            else if dateStr contains "today" then
                return currentDate
            else
                -- Try to parse as date string
                try
                    return date dateStr
                on error
                    return currentDate + 1 * days
                end try
            end if
        end parseCustomDate
        '''

    def _build_applescript_no_date(self, reminder_text, reminder_list, source_info=""):
        """Build AppleScript command without due date"""
        # Add source information to the reminder text if available
        if source_info:
            reminder_text = f"{reminder_text} (from {source_info})"

        return f'''
        tell application "Reminders"
            try
                set targetList to list "{reminder_list}"
            on error
                set targetList to default list
            end try
            
            make new reminder at end of targetList with properties {{name:"{reminder_text}"}}
        end tell
        '''

    def get_reminder_lists(self):
        """Get available reminder lists"""
        try:
            applescript_cmd = '''
            tell application "Reminders"
                set listNames to {}
                repeat with reminderList in lists
                    set end of listNames to name of reminderList
                end repeat
                return listNames
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Parse the returned list
                lists_str = result.stdout.strip()
                if lists_str:
                    # AppleScript returns comma-separated values
                    lists = [list_name.strip()
                             for list_name in lists_str.split(',')]
                    return lists

            return ["Reminders"]  # Default fallback

        except Exception as e:
            logging.error(f"Error getting reminder lists: {e}")
            return ["Reminders"]

    def create_reminder_with_notes(self, reminder_text, due_date=None, notes="", reminder_list=None):
        """Create a reminder with additional notes"""
        try:
            target_list = reminder_list or self.default_list
            reminder_text = self._clean_reminder_text(reminder_text)
            notes = self._clean_reminder_text(notes) if notes else ""

            if due_date and due_date.strip().lower() != 'missing value':
                applescript_cmd = f'''
                tell application "Reminders"
                    try
                        set targetList to list "{target_list}"
                    on error
                        set targetList to default list
                    end try
                    
                    set dueDateObj to {due_date}
                    set newReminder to make new reminder at end of targetList with properties {{name:"{reminder_text}", due date:dueDateObj}}
                    
                    if "{notes}" is not "" then
                        set body of newReminder to "{notes}"
                    end if
                end tell
                '''
            else:
                applescript_cmd = f'''
                tell application "Reminders"
                    try
                        set targetList to list "{target_list}"
                    on error
                        set targetList to default list
                    end try
                    
                    set newReminder to make new reminder at end of targetList with properties {{name:"{reminder_text}"}}
                    
                    if "{notes}" is not "" then
                        set body of newReminder to "{notes}"
                    end if
                end tell
                '''

            result = subprocess.run(
                ['osascript', '-e', applescript_cmd],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown AppleScript error"
                raise Exception(f"AppleScript execution failed: {error_msg}")

            logging.info(
                f"Created reminder with notes: {reminder_text[:30]}...")
            return True

        except Exception as e:
            logging.error(f"Error creating reminder with notes: {e}")
            raise

    def test_reminders_access(self):
        """Test if we can access the Reminders app"""
        try:
            applescript_cmd = '''
            tell application "Reminders"
                return name of default list
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully connected to Reminders app. Default list: {result.stdout.strip()}"
            else:
                return False, f"Failed to connect to Reminders app: {result.stderr}"

        except Exception as e:
            return False, f"Error testing Reminders access: {e}"

    def bulk_create_reminders(self, reminders_list, reminder_list=None):
        """Create multiple reminders efficiently"""
        target_list = reminder_list or self.default_list
        created_count = 0
        errors = []

        for reminder_data in reminders_list:
            try:
                self.create_reminder(reminder_data, target_list)
                created_count += 1
            except Exception as e:
                errors.append(f"Failed to create reminder: {str(e)}")

        return created_count, errors


# import subprocess
# import logging

# # --- Function: Create Reminder via AppleScript ---

# # src/reminder_app/reminder.py
# import subprocess
# import logging


# class ReminderManager:
#     def __init__(self):
#         pass

#     def create_reminder(self, reminder_data):
#         try:
#             reminder_text, due_date = reminder_data

#             if due_date and due_date.strip().lower() == 'missing value':
#                 reminder_cmd = f'''
#                 tell application "Reminders"
#                     set tomorrowDate to (current date) + 1 * days
#                     make new reminder with properties {{name:"{reminder_text}", due date:tomorrowDate}}
#                 end tell
#                 '''
#             elif due_date:
#                 due_date = due_date.strip(': ')
#                 if not ", " in due_date:
#                     reminder_cmd = f'''
#                     tell application "Reminders"
#                         make new reminder with properties {{name:"{reminder_text}", due date: {due_date}}}
#                     end tell
#                     '''
#                 else:
#                     # Include your existing parsing logic here.
#                     reminder_cmd = f'''
#                     tell application "Reminders"
#                         set myDate to current date
#                         if "{due_date}" contains " at " then
#                             set oldDelims to AppleScript's text item delimiters
#                             set AppleScript's text item delimiters to " at "
#                             set datePart to text item 1 of "{due_date}"
#                             set timePart to text item 2 of "{due_date}"
#                             set AppleScript's text item delimiters to oldDelims

#                             set dateComponents to my theSplit(datePart, ", ")
#                             set monthDay to item 1 of dateComponents
#                             set yearStr to item 2 of dateComponents

#                             set year of myDate to yearStr as integer

#                             set monthComponents to my theSplit(monthDay, " ")
#                             set monthName to item 1 of monthComponents
#                             set dayNum to item 2 of monthComponents as integer

#                             if monthName is "January" then
#                                 set month of myDate to 1
#                             else if monthName is "February" then
#                                 set month of myDate to 2
#                             else if monthName is "March" then
#                                 set month of myDate to 3
#                             else if monthName is "April" then
#                                 set month of myDate to 4
#                             else if monthName is "May" then
#                                 set month of myDate to 5
#                             else if monthName is "June" then
#                                 set month of myDate to 6
#                             else if monthName is "July" then
#                                 set month of myDate to 7
#                             else if monthName is "August" then
#                                 set month of myDate to 8
#                             else if monthName is "September" then
#                                 set month of myDate to 9
#                             else if monthName is "October" then
#                                 set month of myDate to 10
#                             else if monthName is "November" then
#                                 set month of myDate to 11
#                             else if monthName is "December" then
#                                 set month of myDate to 12
#                             end if

#                             set day of myDate to dayNum

#                             if timePart contains "PM" then
#                                 set timeStr to text 1 thru -3 of timePart
#                                 set timeComponents to my theSplit(timeStr, ":")
#                                 set hourNum to (item 1 of timeComponents as integer)
#                                 if hourNum ≠ 12 then
#                                     set hourNum to hourNum + 12
#                                 end if
#                                 set hours of myDate to hourNum
#                                 set minutes of myDate to (item 2 of timeComponents as integer)
#                             else if timePart contains "AM" then
#                                 set timeStr to text 1 thru -3 of timePart
#                                 set timeComponents to my theSplit(timeStr, ":")
#                                 set hourNum to (item 1 of timeComponents as integer)
#                                 if hourNum = 12 then
#                                     set hourNum to 0
#                                 end if
#                                 set hours of myDate to hourNum
#                                 set minutes of myDate to (item 2 of timeComponents as integer)
#                             end if
#                         else
#                             set dateComponents to my theSplit("{due_date}", ", ")
#                             set monthDay to item 1 of dateComponents
#                             set yearStr to item 2 of dateComponents

#                             set year of myDate to yearStr as integer

#                             set monthComponents to my theSplit(monthDay, " ")
#                             set monthName to item 1 of monthComponents
#                             set dayNum to item 2 of monthComponents as integer

#                             if monthName is "January" then
#                                 set month of myDate to 1
#                             else if monthName is "February" then
#                                 set month of myDate to 2
#                             else if monthName is "March" then
#                                 set month of myDate to 3
#                             else if monthName is "April" then
#                                 set month of myDate to 4
#                             else if monthName is "May" then
#                                 set month of myDate to 5
#                             else if monthName is "June" then
#                                 set month of myDate to 6
#                             else if monthName is "July" then
#                                 set month of myDate to 7
#                             else if monthName is "August" then
#                                 set month of myDate to 8
#                             else if monthName is "September" then
#                                 set month of myDate to 9
#                             else if monthName is "October" then
#                                 set month of myDate to 10
#                             else if monthName is "November" then
#                                 set month of myDate to 11
#                             else if monthName is "December" then
#                                 set month of myDate to 12
#                             end if

#                             set day of myDate to dayNum
#                             set hours of myDate to 0
#                             set minutes of myDate to 0
#                         end if

#                         make new reminder with properties {{name:"{reminder_text}", due date:myDate}}
#                     end tell

#                     on theSplit(theString, theDelimiter)
#                         set oldDelimiters to AppleScript's text item delimiters
#                         set AppleScript's text item delimiters to theDelimiter
#                         set theArray to every text item of theString
#                         set AppleScript's text item delimiters to oldDelimiters
#                         return theArray
#                     end theSplit
#                     '''
#             else:
#                 reminder_cmd = f'''
#                 tell application "Reminders"
#                     make new reminder with properties {{name:"{reminder_text}"}}
#                 end tell
#                 '''
#             subprocess.call(['osascript', '-e', reminder_cmd])
#             logging.info(
#                 f"Created reminder: {reminder_text} (Due: {due_date if due_date else 'Not specified'})")
#         except Exception as e:
#             logging.error(f"Error creating reminder: {e}")
