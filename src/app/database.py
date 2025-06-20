# src/reminder_app/database.py
import sqlite3
import pandas as pd
import os
import logging


class MessageDB:
    def __init__(self, db_path=None):
        # Allow overriding the default path for testing or customization
        self.db_path = db_path or os.path.expanduser(
            "~/Library/Messages/chat.db")
        self.contacts_cache = {}

    def get_contact_name(self, handle_id):
        """Get contact name from handle ID with caching"""
        if handle_id in self.contacts_cache:
            return self.contacts_cache[handle_id]

        try:
            # Try to get the contact name from the AddressBook database
            # This is a simplified version - macOS contacts integration can be complex
            conn = sqlite3.connect(self.db_path)

            # First try to get from the handle table itself
            query = """
            SELECT DISTINCT handle.id, handle.person_centric_id
            FROM handle 
            WHERE handle.rowid = ?
            """

            cursor = conn.cursor()
            cursor.execute(query, (handle_id,))
            result = cursor.fetchone()

            if result:
                phone_email = result[0]
                # Clean up phone numbers for better display
                if phone_email and not '@' in phone_email:
                    # It's a phone number
                    clean_number = ''.join(filter(str.isdigit, phone_email))
                    if len(clean_number) >= 10:
                        if len(clean_number) == 10:
                            formatted = f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
                        elif len(clean_number) == 11 and clean_number[0] == '1':
                            formatted = f"+1 ({clean_number[1:4]}) {clean_number[4:7]}-{clean_number[7:]}"
                        else:
                            formatted = phone_email
                        self.contacts_cache[handle_id] = formatted
                        return formatted

                # It's an email or we couldn't format the phone
                self.contacts_cache[handle_id] = phone_email
                return phone_email

            conn.close()

        except Exception as e:
            logging.warning(
                f"Could not resolve contact name for handle {handle_id}: {e}")

        # Fallback
        self.contacts_cache[handle_id] = f"Unknown ({handle_id})"
        return self.contacts_cache[handle_id]

    def get_unread_imessages(self, limit=50):
        """Get unread iMessages with better contact resolution"""
        query = """
        SELECT
            message.rowid,
            message.text,
            message.is_read,
            handle.id as sender,
            handle.rowid as handle_id,
            datetime(message.date/1000000000 + 978307200, 'unixepoch', 'localtime') AS sent_date,
            message.service,
            CASE 
                WHEN message.is_from_me = 1 THEN 'Sent'
                ELSE 'Received'
            END as direction
        FROM message
        JOIN handle ON message.handle_id = handle.rowid
        WHERE message.is_read = 0
          AND message.text IS NOT NULL
          AND message.text != ''
          AND message.is_from_me = 0
          AND message.service IN ('iMessage', 'SMS')
        ORDER BY message.date DESC
        LIMIT ?;
        """
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(query, conn, params=[limit])
            conn.close()

            # Add contact names
            if not df.empty:
                df['contact_name'] = df.apply(
                    lambda row: self.resolve_contact_display_name(
                        row['sender']),
                    axis=1
                )

            return df
        except Exception as e:
            raise Exception(f"Error accessing Messages database: {e}")

    def resolve_contact_display_name(self, sender_id):
        """Resolve sender ID to a nice display name"""
        try:
            # Check if it's a phone number
            if sender_id and not '@' in str(sender_id):
                # Clean and format phone number
                clean_number = ''.join(filter(str.isdigit, str(sender_id)))
                if len(clean_number) >= 10:
                    if len(clean_number) == 10:
                        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
                    elif len(clean_number) == 11 and clean_number[0] == '1':
                        return f"+1 ({clean_number[1:4]}) {clean_number[4:7]}-{clean_number[7:]}"

            # If it's an email or couldn't format, return as-is
            return str(sender_id) if sender_id else "Unknown"

        except Exception:
            return "Unknown"

    def mark_messages_as_read(self, message_ids):
        """Mark specific messages as read (optional feature)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Note: Be very careful with this - it modifies the Messages database
            placeholders = ','.join(['?' for _ in message_ids])
            query = f"UPDATE message SET is_read = 1 WHERE rowid IN ({placeholders})"

            cursor.execute(query, message_ids)
            conn.commit()
            conn.close()

            logging.info(f"Marked {len(message_ids)} messages as read")

        except Exception as e:
            logging.error(f"Error marking messages as read: {e}")
            raise

    def get_conversation_context(self, sender_id, limit=5):
        """Get recent conversation context for better reminder generation"""
        query = """
        SELECT
            message.text,
            message.is_from_me,
            datetime(message.date/1000000000 + 978307200, 'unixepoch', 'localtime') AS sent_date
        FROM message
        JOIN handle ON message.handle_id = handle.rowid
        WHERE handle.id = ?
          AND message.text IS NOT NULL
          AND message.text != ''
        ORDER BY message.date DESC
        LIMIT ?;
        """

        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(query, conn, params=[sender_id, limit])
            conn.close()
            return df
        except Exception as e:
            logging.error(f"Error getting conversation context: {e}")
            return pd.DataFrame()

    def get_statistics(self):
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            # Total messages
            cursor.execute(
                "SELECT COUNT(*) FROM message WHERE text IS NOT NULL")
            stats['total_messages'] = cursor.fetchone()[0]

            # Unread messages
            cursor.execute(
                "SELECT COUNT(*) FROM message WHERE is_read = 0 AND text IS NOT NULL AND is_from_me = 0")
            stats['unread_messages'] = cursor.fetchone()[0]

            # Unique contacts
            cursor.execute(
                "SELECT COUNT(DISTINCT handle_id) FROM message WHERE is_from_me = 0")
            stats['unique_contacts'] = cursor.fetchone()[0]

            # Messages today
            cursor.execute("""
                SELECT COUNT(*) FROM message 
                WHERE date >= (strftime('%s', 'now', 'start of day') - 978307200) * 1000000000
                AND text IS NOT NULL
                AND is_from_me = 0
            """)
            stats['messages_today'] = cursor.fetchone()[0]

            conn.close()
            return stats

        except Exception as e:
            logging.error(f"Error getting statistics: {e}")
            return {}


# import sqlite3
# import pandas as pd
# import os


# class MessageDB:
#     def __init__(self, db_path=None):
#         # Allow overriding the default path for testing or customization
#         self.db_path = db_path or os.path.expanduser(
#             "~/Library/Messages/chat.db")

#     def get_unread_imessages(self):
#         query = """
#         SELECT
#             message.rowid,
#             message.text,
#             message.is_read,
#             handle.id as sender,
#             datetime(message.date/1000000000 + 978307200, 'unixepoch', 'localtime') AS sent_date
#         FROM message
#         JOIN handle ON message.handle_id = handle.rowid
#         WHERE message.is_read = 0
#           AND message.text IS NOT NULL
#           AND message.is_from_me = 0
#         ORDER BY message.date DESC;
#         """
#         try:
#             conn = sqlite3.connect(self.db_path)
#             df = pd.read_sql_query(query, conn)
#             conn.close()
#             return df
#         except Exception as e:
#             raise Exception(f"Error accessing Messages database: {e}")
