# src/reminder_app/ui.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont
import logging
import time
import pandas as pd
from datetime import datetime, timedelta
import re
from database import MessageDB
from llm import GeminiLLM
from reminder import ReminderManager


class ReminderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Reminder Assistant")
        self.root.geometry("1000x700")
        self.root.configure(bg='#f0f0f0')

        # Configure styles
        self.setup_styles()

        # Initialize components
        self.db = MessageDB()
        self.llm = GeminiLLM()
        self.rm = ReminderManager()

        # Storage for staged reminders
        self.staged_reminders = []

        # Create main interface
        self.create_main_interface()

        # Auto-refresh every 30 seconds
        self.auto_refresh()

    def setup_styles(self):
        """Configure custom styles for the application"""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure custom styles
        self.style.configure('Title.TLabel', font=(
            'Helvetica', 16, 'bold'), background='#f0f0f0')
        self.style.configure('Header.TLabel', font=(
            'Helvetica', 12, 'bold'), background='#f0f0f0')
        self.style.configure('Success.TButton', background='#4CAF50')
        self.style.configure('Warning.TButton', background='#FF9800')
        self.style.configure('Danger.TButton', background='#f44336')

    def create_main_interface(self):
        """Create the main application interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="📱 Smart Reminder Assistant",
                                style='Title.TLabel')
        title_label.pack(pady=(0, 20))

        # Stats frame
        self.create_stats_frame(main_frame)

        # Control buttons frame
        self.create_control_frame(main_frame)

        # Main content area with tabs
        self.create_tabbed_interface(main_frame)

        # Status bar
        self.create_status_bar(main_frame)

    def create_stats_frame(self, parent):
        """Create stats display frame"""
        stats_frame = ttk.LabelFrame(parent, text="📊 Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 15))

        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill=tk.X)

        # Stats labels
        self.unread_count_label = ttk.Label(stats_inner, text="Unread Messages: 0",
                                            font=('Helvetica', 10, 'bold'))
        self.unread_count_label.pack(side=tk.LEFT, padx=(0, 20))

        self.staged_count_label = ttk.Label(stats_inner, text="Staged Reminders: 0",
                                            font=('Helvetica', 10, 'bold'))
        self.staged_count_label.pack(side=tk.LEFT, padx=(0, 20))

        self.last_update_label = ttk.Label(stats_inner, text="Last Updated: Never",
                                           font=('Helvetica', 9))
        self.last_update_label.pack(side=tk.RIGHT)

    def create_control_frame(self, parent):
        """Create control buttons frame"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(0, 15))

        # Process messages button
        self.process_btn = ttk.Button(control_frame, text="🔄 Scan & Process Messages",
                                      command=self.process_messages, style='Success.TButton')
        self.process_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Refresh button
        refresh_btn = ttk.Button(control_frame, text="↻ Refresh",
                                 command=self.refresh_data)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Clear staged button
        clear_btn = ttk.Button(control_frame, text="🗑 Clear Staged",
                               command=self.clear_staged_reminders, style='Warning.TButton')
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Settings button
        settings_btn = ttk.Button(control_frame, text="⚙ Settings",
                                  command=self.open_settings)
        settings_btn.pack(side=tk.RIGHT)

    def create_tabbed_interface(self, parent):
        """Create tabbed interface for different views"""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Messages tab
        self.messages_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.messages_frame, text="📥 Recent Messages")
        self.create_messages_tab()

        # Staged reminders tab
        self.staged_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.staged_frame, text="📝 Staged Reminders")
        self.create_staged_tab()

        # History tab
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="📜 History")
        self.create_history_tab()

    def create_messages_tab(self):
        """Create the messages display tab"""
        # Messages list with scrollbar
        list_frame = ttk.Frame(self.messages_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create Treeview for better display
        columns = ('Sender', 'Message', 'Date', 'Status')
        self.messages_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.messages_tree.heading('Sender', text='From')
        self.messages_tree.heading('Message', text='Message Preview')
        self.messages_tree.heading('Date', text='Received')
        self.messages_tree.heading('Status', text='Status')

        self.messages_tree.column('Sender', width=150)
        self.messages_tree.column('Message', width=400)
        self.messages_tree.column('Date', width=150)
        self.messages_tree.column('Status', width=100)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.messages_tree.yview)
        h_scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.HORIZONTAL, command=self.messages_tree.xview)
        self.messages_tree.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack everything
        self.messages_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_staged_tab(self):
        """Create the staged reminders tab"""
        # Top frame for controls
        top_frame = ttk.Frame(self.staged_frame)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(top_frame, text="Staged Reminders - Review and Edit Before Creating",
                  style='Header.TLabel').pack(side=tk.LEFT)

        # Create all button
        create_all_btn = ttk.Button(top_frame, text="✅ Create All Reminders",
                                    command=self.create_all_reminders, style='Success.TButton')
        create_all_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Staged reminders list
        staged_list_frame = ttk.Frame(self.staged_frame)
        staged_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create frame for staged reminders with scrolling
        canvas = tk.Canvas(staged_list_frame, bg='white')
        scrollbar_staged = ttk.Scrollbar(
            staged_list_frame, orient="vertical", command=canvas.yview)
        self.staged_scrollable_frame = ttk.Frame(canvas)

        self.staged_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window(
            (0, 0), window=self.staged_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_staged.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_staged.pack(side="right", fill="y")

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)

    def create_history_tab(self):
        """Create the history tab"""
        ttk.Label(self.history_frame, text="📜 Recent Activity",
                  style='Header.TLabel').pack(pady=10)

        # History list
        self.history_text = tk.Text(self.history_frame, height=20, wrap=tk.WORD,
                                    font=('Consolas', 9), bg='#f8f8f8')
        history_scroll = ttk.Scrollbar(
            self.history_frame, command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=history_scroll.set)

        self.history_text.pack(side=tk.LEFT, fill=tk.BOTH,
                               expand=True, padx=(10, 0), pady=10)
        history_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)

        # Add some initial history
        self.add_to_history("Application started")

    def create_status_bar(self, parent):
        """Create status bar at the bottom"""
        self.status_bar = ttk.Label(
            parent, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def update_status(self, message):
        """Update the status bar message"""
        self.status_bar.config(
            text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
        self.root.update_idletasks()

    def add_to_history(self, message):
        """Add a message to the history log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.history_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.history_text.see(tk.END)

    def resolve_contact_name(self, phone_or_email):
        """Resolve phone number or email to contact name"""
        # This is a simplified version - you might want to integrate with
        # the Contacts app or maintain your own contact database
        try:
            # Remove formatting from phone numbers
            clean_number = re.sub(r'[^\d+]', '', str(phone_or_email))

            # You could add logic here to query the Contacts database
            # For now, we'll just clean up the display
            if '@' in str(phone_or_email):
                return phone_or_email  # It's an email
            elif len(clean_number) >= 10:
                # Format phone number nicely
                if len(clean_number) == 10:
                    return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
                elif len(clean_number) == 11 and clean_number[0] == '1':
                    return f"+1 ({clean_number[1:4]}) {clean_number[4:7]}-{clean_number[7:]}"

            return phone_or_email
        except:
            return phone_or_email

    def refresh_data(self):
        """Refresh the messages display"""
        self.update_status("Refreshing data...")
        try:
            df = self.db.get_unread_imessages()
            self.populate_messages_tree(df)
            self.update_stats(len(df))
            self.update_status("Data refreshed successfully")
            self.add_to_history(
                f"Refreshed data - {len(df)} unread messages found")
        except Exception as e:
            self.update_status(f"Error refreshing data: {str(e)}")
            messagebox.showerror("Error", f"Failed to refresh data: {str(e)}")

    def populate_messages_tree(self, df):
        """Populate the messages tree view"""
        # Clear existing items
        for item in self.messages_tree.get_children():
            self.messages_tree.delete(item)

        for _, row in df.iterrows():
            sender = self.resolve_contact_name(row.get("sender", "Unknown"))
            message_preview = (
                row["text"][:50] + "...") if len(row["text"]) > 50 else row["text"]
            date_str = row.get("sent_date", "Unknown")

            self.messages_tree.insert('', tk.END, values=(
                sender, message_preview, date_str, "Unread"))

    def update_stats(self, unread_count):
        """Update the statistics display"""
        self.unread_count_label.config(text=f"Unread Messages: {unread_count}")
        self.staged_count_label.config(
            text=f"Staged Reminders: {len(self.staged_reminders)}")
        self.last_update_label.config(
            text=f"Last Updated: {datetime.now().strftime('%H:%M:%S')}")

    def process_messages(self):
        """Process unread messages and create staged reminders"""
        self.update_status("Processing messages...")
        self.process_btn.config(state='disabled', text="Processing...")

        try:
            df = self.db.get_unread_imessages()
        except Exception as e:
            messagebox.showerror("Database Error", str(e))
            self.process_btn.config(
                state='normal', text="🔄 Scan & Process Messages")
            return

        if df.empty:
            messagebox.showinfo("Info", "No unread messages found.")
            self.process_btn.config(
                state='normal', text="🔄 Scan & Process Messages")
            return

        # Process messages and create staged reminders
        processed_count = 0
        for _, row in df.iterrows():
            try:
                sender = row.get("sender", "Unknown")
                text = row["text"]

                self.update_status(f"Processing message from {sender}...")
                result = self.llm.generate_reminder(text, sender)

                if result:
                    reminder_text, due_date, sender = result
                    contact_name = self.resolve_contact_name(sender)

                    # Create staged reminder
                    staged_reminder = {
                        'original_text': text,
                        'reminder_text': reminder_text,
                        'due_date': due_date,
                        'sender': sender,
                        'contact_name': contact_name,
                        'created_at': datetime.now()
                    }

                    self.staged_reminders.append(staged_reminder)
                    processed_count += 1

                time.sleep(0.5)  # Brief delay to avoid API rate limits

            except Exception as e:
                logging.error(f"Failed to process message: {e}")
                self.add_to_history(
                    f"Error processing message from {sender}: {str(e)}")

        # Update UI
        self.refresh_staged_reminders_display()
        self.update_stats(len(df))

        if processed_count > 0:
            self.notebook.select(1)  # Switch to staged reminders tab
            messagebox.showinfo(
                "Success", f"Created {processed_count} staged reminders!")
            self.add_to_history(
                f"Processed {processed_count} messages into staged reminders")
        else:
            messagebox.showinfo(
                "Info", "No action items detected in messages.")
            self.add_to_history("No action items found in processed messages")

        self.process_btn.config(
            state='normal', text="🔄 Scan & Process Messages")
        self.update_status("Processing complete")

    def refresh_staged_reminders_display(self):
        """Refresh the staged reminders display"""
        # Clear existing widgets
        for widget in self.staged_scrollable_frame.winfo_children():
            widget.destroy()

        for i, reminder in enumerate(self.staged_reminders):
            self.create_staged_reminder_widget(reminder, i)

    def create_staged_reminder_widget(self, reminder, index):
        """Create a widget for a staged reminder"""
        # Main frame for this reminder
        reminder_frame = ttk.LabelFrame(self.staged_scrollable_frame,
                                        text=f"Reminder from {reminder['contact_name']}",
                                        padding=10)
        reminder_frame.pack(fill=tk.X, padx=5, pady=5)

        # Original message display
        orig_frame = ttk.Frame(reminder_frame)
        orig_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(orig_frame, text="Original Message:", font=(
            'Helvetica', 9, 'bold')).pack(anchor=tk.W)
        orig_text = tk.Text(orig_frame, height=2,
                            wrap=tk.WORD, font=('Helvetica', 9))
        orig_text.insert('1.0', reminder['original_text'])
        orig_text.config(state='disabled', bg='#f0f0f0')
        orig_text.pack(fill=tk.X, pady=(2, 0))

        # Editable reminder text
        reminder_edit_frame = ttk.Frame(reminder_frame)
        reminder_edit_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(reminder_edit_frame, text="Reminder Text:",
                  font=('Helvetica', 9, 'bold')).pack(anchor=tk.W)
        reminder_text_var = tk.StringVar(value=reminder['reminder_text'])
        reminder_entry = ttk.Entry(
            reminder_edit_frame, textvariable=reminder_text_var, font=('Helvetica', 10))
        reminder_entry.pack(fill=tk.X, pady=(2, 0))

        # Due date editing
        date_frame = ttk.Frame(reminder_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text="Due Date:", font=(
            'Helvetica', 9, 'bold')).pack(side=tk.LEFT)

        due_date_var = tk.StringVar(
            value=reminder['due_date'] if reminder['due_date'] != 'missing value' else '')
        due_date_entry = ttk.Entry(
            date_frame, textvariable=due_date_var, width=20)
        due_date_entry.pack(side=tk.LEFT, padx=(10, 5))

        # Quick date buttons
        ttk.Button(date_frame, text="Today",
                   command=lambda: due_date_var.set(datetime.now().strftime("date \"%m/%d/%Y 12:00 PM\""))).pack(side=tk.LEFT, padx=2)
        ttk.Button(date_frame, text="Tomorrow",
                   command=lambda: due_date_var.set((datetime.now() + timedelta(days=1)).strftime("date \"%m/%d/%Y 12:00 PM\""))).pack(side=tk.LEFT, padx=2)
        ttk.Button(date_frame, text="Next Week",
                   command=lambda: due_date_var.set((datetime.now() + timedelta(weeks=1)).strftime("date \"%m/%d/%Y 12:00 PM\""))).pack(side=tk.LEFT, padx=2)

        # Action buttons
        action_frame = ttk.Frame(reminder_frame)
        action_frame.pack(fill=tk.X)

        # Update the reminder data when values change
        def update_reminder():
            self.staged_reminders[index]['reminder_text'] = reminder_text_var.get(
            )
            self.staged_reminders[index]['due_date'] = due_date_var.get(
            ) if due_date_var.get() else 'missing value'

        # Create individual reminder button
        create_btn = ttk.Button(action_frame, text="✅ Create This Reminder",
                                command=lambda: self.create_individual_reminder(
                                    index, update_reminder),
                                style='Success.TButton')
        create_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Remove reminder button
        remove_btn = ttk.Button(action_frame, text="❌ Remove",
                                command=lambda: self.remove_staged_reminder(
                                    index),
                                style='Danger.TButton')
        remove_btn.pack(side=tk.LEFT)

        # Info label
        info_text = f"From: {reminder['sender']} | Created: {reminder['created_at'].strftime('%H:%M:%S')}"
        ttk.Label(action_frame, text=info_text, font=(
            'Helvetica', 8), foreground='gray').pack(side=tk.RIGHT)

    def create_individual_reminder(self, index, update_callback):
        """Create a single reminder"""
        update_callback()  # Update the reminder data

        reminder = self.staged_reminders[index]
        try:
            self.rm.create_reminder(
                (reminder['reminder_text'], reminder['due_date']))
            self.add_to_history(
                f"Created reminder: {reminder['reminder_text'][:50]}...")

            # Remove from staged list
            self.staged_reminders.pop(index)
            self.refresh_staged_reminders_display()
            self.update_stats(0)  # Update count

            messagebox.showinfo("Success", "Reminder created successfully!")

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to create reminder: {str(e)}")
            self.add_to_history(f"Error creating reminder: {str(e)}")

    def remove_staged_reminder(self, index):
        """Remove a staged reminder"""
        if messagebox.askyesno("Confirm", "Remove this staged reminder?"):
            removed = self.staged_reminders.pop(index)
            self.refresh_staged_reminders_display()
            self.update_stats(0)
            self.add_to_history(
                f"Removed staged reminder: {removed['reminder_text'][:50]}...")

    def create_all_reminders(self):
        """Create all staged reminders"""
        if not self.staged_reminders:
            messagebox.showinfo("Info", "No staged reminders to create.")
            return

        if not messagebox.askyesno("Confirm", f"Create all {len(self.staged_reminders)} staged reminders?"):
            return

        created_count = 0
        errors = []

        # Copy list to avoid modification issues
        for reminder in self.staged_reminders[:]:
            try:
                self.rm.create_reminder(
                    (reminder['reminder_text'], reminder['due_date']))
                created_count += 1
                self.add_to_history(
                    f"Created reminder: {reminder['reminder_text'][:50]}...")
            except Exception as e:
                errors.append(
                    f"Failed to create '{reminder['reminder_text'][:30]}...': {str(e)}")

        # Clear all staged reminders
        self.staged_reminders.clear()
        self.refresh_staged_reminders_display()
        self.update_stats(0)

        # Show results
        if errors:
            error_msg = f"Created {created_count} reminders.\nErrors:\n" + \
                "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more errors"
            messagebox.showwarning("Partial Success", error_msg)
        else:
            messagebox.showinfo(
                "Success", f"Successfully created all {created_count} reminders!")

    def clear_staged_reminders(self):
        """Clear all staged reminders"""
        if not self.staged_reminders:
            messagebox.showinfo("Info", "No staged reminders to clear.")
            return

        if messagebox.askyesno("Confirm", f"Clear all {len(self.staged_reminders)} staged reminders?"):
            count = len(self.staged_reminders)
            self.staged_reminders.clear()
            self.refresh_staged_reminders_display()
            self.update_stats(0)
            self.add_to_history(f"Cleared {count} staged reminders")

    def open_settings(self):
        """Open settings dialog"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("400x300")
        settings_win.transient(self.root)
        settings_win.grab_set()

        ttk.Label(settings_win, text="Settings", font=(
            'Helvetica', 14, 'bold')).pack(pady=10)

        # Placeholder for settings
        ttk.Label(settings_win, text="Auto-refresh interval:").pack(pady=5)
        ttk.Scale(settings_win, from_=10, to=300,
                  orient=tk.HORIZONTAL).pack(pady=5)

        ttk.Label(settings_win, text="Default reminder time:").pack(pady=5)
        ttk.Combobox(settings_win, values=[
                     "9:00 AM", "12:00 PM", "3:00 PM", "6:00 PM"]).pack(pady=5)

        ttk.Button(settings_win, text="Save",
                   command=settings_win.destroy).pack(pady=20)

    def auto_refresh(self):
        """Auto-refresh functionality"""
        try:
            # Only refresh if we're on the messages tab and no processing is happening
            if (self.notebook.index(self.notebook.select()) == 0 and
                    self.process_btn['state'] != 'disabled'):
                self.refresh_data()
        except:
            pass  # Ignore errors during auto-refresh

        # Schedule next refresh in 30 seconds
        self.root.after(30000, self.auto_refresh)

# # src/reminder_app/ui.py
# import tkinter as tk
# from tkinter import ttk, messagebox
# import logging
# import time
# import pandas as pd
# from database import MessageDB
# from llm import GeminiLLM
# from reminder import ReminderManager


# class ReminderUI:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("Action Item Reminder App")
#         self.root.geometry("700x500")
#         self.frame = ttk.Frame(self.root, padding=10)
#         self.frame.pack(expand=True, fill=tk.BOTH)
#         ttk.Label(self.frame, text="Unread Messages & Generated Reminders",
#                   font=("Helvetica", 14)).pack(pady=10)
#         self.listbox = tk.Listbox(self.frame, width=80, height=20)
#         self.listbox.pack(pady=10)
#         self.process_btn = ttk.Button(
#             self.frame, text="Process Messages", command=self.process_messages)
#         self.process_btn.pack(pady=10)

#         # Initialize our components
#         self.db = MessageDB()
#         self.llm = GeminiLLM()
#         self.rm = ReminderManager()

#     def process_messages(self, batch_size=5):
#         try:
#             df = self.db.get_unread_imessages()
#         except Exception as e:
#             messagebox.showerror("Database Error", str(e))
#             return

#         if df.empty:
#             messagebox.showinfo("Info", "No unread messages found.")
#             return

#         # Open review/edit window
#         self.open_review_window(df)

#     def open_review_window(self, df):
#         review_win = tk.Toplevel(self.root)
#         review_win.title("Review & Edit Messages")
#         review_win.geometry("800x600")
#         frame = ttk.Frame(review_win, padding=10)
#         frame.pack(expand=True, fill=tk.BOTH)
#         ttk.Label(frame, text="Edit messages before creating reminders:",
#                   font=("Helvetica", 14)).pack(pady=10)

#         canvas = tk.Canvas(frame)
#         scrollbar = ttk.Scrollbar(
#             frame, orient="vertical", command=canvas.yview)
#         scrollable_frame = ttk.Frame(canvas)

#         scrollable_frame.bind(
#             "<Configure>",
#             lambda e: canvas.configure(
#                 scrollregion=canvas.bbox("all")
#             )
#         )

#         canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
#         canvas.configure(yscrollcommand=scrollbar.set, height=400)

#         canvas.pack(side="left", fill="both", expand=True)
#         scrollbar.pack(side="right", fill="y")

#         self.edit_entries = []
#         for idx, row in df.iterrows():
#             sender = row.get("sender", "Unknown")
#             text = row["text"]
#             msg_frame = ttk.Frame(scrollable_frame, padding=5)
#             msg_frame.pack(fill=tk.X, pady=2)
#             ttk.Label(msg_frame, text=f"From: {sender}", width=20).pack(
#                 side=tk.LEFT)
#             entry = ttk.Entry(msg_frame, width=80)
#             entry.insert(0, text)
#             entry.pack(side=tk.LEFT, padx=5)
#             self.edit_entries.append((entry, sender))

#         process_btn = ttk.Button(frame, text="Create Reminders",
#                                  command=lambda: self.process_edited_messages(review_win))
#         process_btn.pack(pady=15)

#     def process_edited_messages(self, review_win, batch_size=5):
#         review_win.destroy()
#         reminders = []
#         self.listbox.delete(0, tk.END)
#         for entry, sender in self.edit_entries:
#             text = entry.get()
#             if not text or not text.strip():
#                 continue
#             logging.info(f"Processing message from {sender}: {text[:50]}...")
#             try:
#                 result = self.llm.generate_reminder(text, sender)
#                 if result:
#                     reminders.append(result)
#                     self.rm.create_reminder(result)
#             except Exception as e:
#                 logging.error(f"Failed to process message: {e}")
#             time.sleep(1)  # Reduce sleep for UI responsiveness

#         if reminders:
#             for r in reminders:
#                 reminder_text, due, sender = r
#                 due_display = due if due else "Not specified"
#                 display_text = f"From {sender}: {reminder_text} (Due: {due_display})"
#                 self.listbox.insert(tk.END, display_text)
#                 logging.info(f"Created reminder: {display_text}")
#             messagebox.showinfo(
#                 "Success", f"Created {len(reminders)} reminders.")
#         else:
#             messagebox.showinfo("Info", "No action items detected.")
