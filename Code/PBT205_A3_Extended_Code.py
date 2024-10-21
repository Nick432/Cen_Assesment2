import pika
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
import sqlite3
import re
from PIL import Image, ImageTk
import hashlib

# database setup: this creates a SQLite database and a table for storing user credentials if not already present
conn = sqlite3.connect('chat_users.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )
''')
conn.commit()
conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class ChatClient:
    def __init__(self, username, room):
        self.username = username
        self.room = room

        # establish a connection to RabbitMQ server
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()

        # declare an exchange and queue for the chat room
        self.channel.exchange_declare(exchange=self.room, exchange_type='fanout')
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.queue_name = result.method.queue
        self.channel.queue_bind(exchange=self.room, queue=self.queue_name)

        # create the main GUI window
        self.root = tk.Tk()
        self.root.title(f"Chat Room - {self.username} ({self.room})")
        self.root.configure(bg='#2E2E2E')

        # create and configure the chat area
        self.chat_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state='disabled', bg='#1E1E1E', fg='#FFFFFF', font=('Arial', 12))
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # define text formatting tags for different styles and colours
        self.chat_area.tag_config('colour_red', foreground='#FF0000')
        self.chat_area.tag_config('colour_blue', foreground='#0000FF')
        self.chat_area.tag_config('colour_green', foreground='#00FF00')
        self.chat_area.tag_config('bold', font=('Arial', 12, 'bold'))
        self.chat_area.tag_config('italic', font=('Arial', 12, 'italic'))
        self.chat_area.tag_config('colour_yellow', foreground='#FFFF00')
        self.chat_area.tag_config('colour_purple', foreground='#800080')
        self.chat_area.tag_config('colour_orange', foreground='#FFA500')
        self.chat_area.tag_config('colour_cyan', foreground='#00FFFF')
        self.chat_area.tag_config('colour_magenta', foreground='#FF00FF')

        # create the message entry field
        entry_frame = tk.Frame(self.root, bg='#2E2E2E')
        entry_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=False)

        self.message_entry = tk.Entry(entry_frame, bg='#1E1E1E', fg='#FFFFFF', insertbackground='#FFFFFF', bd=0, font=('Arial', 12))
        self.message_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", self.send_message)

        # create and configure the send button
        self.send_button = tk.Button(entry_frame, text="Send", command=self.send_message, bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 12))
        self.send_button.pack(side=tk.RIGHT, padx=10)

        # create and configure the emoji button
        self.emoji_button = tk.Button(entry_frame, text="😊", command=self.open_emoji_picker, bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 12))
        self.emoji_button.pack(side=tk.RIGHT, padx=5)

        # set behavior on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # send a system join message
        self.send_system_message(f"{self.username} has joined the chat. Welcome {self.username}! Use !commands to get started.")

        # start a RabbitMQ thread to receive messages
        self.receive_thread = threading.Thread(target=self.receive_messages)
        self.receive_thread.start()

        # start the main GUI loop
        self.root.mainloop()

    def send_message(self, event=None):
        message = self.message_entry.get()
        if message.strip():
            # handle whisper (private) messages
            if message.startswith('!whisper'):
                parts = message.split(' ', 2)
                if len(parts) >= 3:
                    recipient = parts[1]
                    whisper_message = parts[2]
                    self.channel.basic_publish(
                        exchange=self.room,
                        routing_key='',
                        body=f'WHISPER|{self.username}|{recipient}|{whisper_message}'
                    )
                    # for sending the users whisper messages in the chat area
                    self.update_chat_area(f"[Whisper to {recipient}]: {whisper_message}")
                else:
                    messagebox.showerror("Error", "Invalid whisper format. Use !whisper <username> <message>") # error message for improper command usage
            elif message == '!commands':
                self.show_commands() # show all available commands
            else:
                # for sending the users public messages in the chat area
                self.channel.basic_publish(
                    exchange=self.room,
                    routing_key='',
                    body=f'PUBLIC|{self.username}|{message}'
                )
            self.message_entry.delete(0, tk.END) # clear the message entry field when a message is sent

    def parse_and_insert(self, message):
        self.chat_area.config(state='normal')

        words = message.split(' ')
        colour_tag = None
        bold_active = False
        italic_active = False

        def apply_tags(word, tags):
            # apply the word with the tags to the chat area
            self.chat_area.insert(tk.END, word, tags)

        for i, word in enumerate(words):
            current_word = word
            tags = []

            # check for colour commands 
            if current_word.startswith('!red'):
                colour_tag = 'colour_red'
                current_word = current_word[4:]
            elif current_word.startswith('!blue'):
                colour_tag = 'colour_blue'
                current_word = current_word[5:]
            elif current_word.startswith('!green'):
                colour_tag = 'colour_green'
                current_word = current_word[6:]
            elif current_word.startswith('!yellow'):
                colour_tag = 'colour_yellow'
                current_word = current_word[7:]
            elif current_word.startswith('!purple'):
                colour_tag = 'colour_purple'
                current_word = current_word[7:]
            elif current_word.startswith('!orange'):
                colour_tag = 'colour_orange'
                current_word = current_word[7:]
            elif current_word.startswith('!cyan'):
                colour_tag = 'colour_cyan'
                current_word = current_word[5:]
            elif current_word.startswith('!magenta'):
                colour_tag = 'colour_magenta'
                current_word = current_word[8:]

            # process bold/italic markers
            if current_word.startswith('**') and current_word.endswith('**'):
                bold_active = True
                current_word = current_word[2:-2]
            elif current_word.startswith('**'):
                bold_active = True
                current_word = current_word[2:]
            elif current_word.endswith('**'):
                bold_active = True
                current_word = current_word[:-2]
            elif '**' in current_word:
                parts = current_word.split('**')
                current_word = parts[0]
                bold_active = True
                apply_tags(current_word, tags)
                current_word = parts[1]

            if current_word.startswith('*') and current_word.endswith('*'):
                italic_active = True
                current_word = current_word[1:-1]
            elif current_word.startswith('*'):
                italic_active = True
                current_word = current_word[1:]
            elif current_word.endswith('*'):
                italic_active = True
                current_word = current_word[:-1]

            # apply accumulated tags (colour, bold, italic) to the message
            if colour_tag:
                tags.append(colour_tag)
            if bold_active:
                tags.append('bold')
            if italic_active:
                tags.append('italic')

            apply_tags(current_word, tags)
            
            # add space between words
            if i < len(words) - 1:
                self.chat_area.insert(tk.END, " ")

        # move to a new line after the message is sent
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def send_system_message(self, message):
        # send a system message (e.g. user has joined/left the chat)
        self.channel.basic_publish(
            exchange=self.room,
            routing_key='',
            body=f'SYSTEM|{message}'
        )

    def receive_messages(self):
        # callback function to handle incoming messages
        def callback(ch, method, properties, body):
            message = body.decode()
            message_parts = message.split('|')
            if message_parts[0] == 'WHISPER':
                _, sender, recipient, whisper_message = message_parts
                if recipient == self.username:
                    self.root.after(0, self.update_chat_area, f"[Whisper from {sender}]: {whisper_message}")
            elif message_parts[0] == 'PUBLIC':
                _, sender, public_message = message_parts
                self.root.after(0, self.update_chat_area, f"{sender}: {public_message}")
            elif message_parts[0] == 'SYSTEM':
                _, system_message = message_parts
                self.root.after(0, self.update_chat_area, f"SYSTEM: {system_message}")

        # start consuming messages from the RabbitMQ queue
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=callback, auto_ack=True)
        self.channel.start_consuming()

    # add the received message to the chat area with formatting
    def update_chat_area(self, message, literal=False):
        self.chat_area.config(state='normal')

        if literal:
            self.chat_area.insert(tk.END, message + "\n")
        else:
            self.parse_and_insert(message)

        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    # print all available commands to the users chat from the system
    def show_commands(self):
        commands = (
            "List of all available commands are below.\n"
            "!whisper <username> <message>: Send a private message to a user.\n"
            "!<colour> <message>: Make the message text a certain colour. Available colours: Red, Blue, Green, Yellow, Purple, Orange, Cyan, Magenta.\n"
            "Italic Text: Use '*' before and after your text to make it italic.\n"
            "Bold Text: Use '**' before and after your text to make it bold.\n"
        )
        self.update_chat_area("SYSTEM: " + commands, literal=True)

    def open_emoji_picker(self):
        # pop-up window for emoji selection
        emoji_window = tk.Toplevel(self.root)
        emoji_window.title("Emoji Picker")
        emoji_window.configure(bg='#2E2E2E')

        emojis = [
            "😊", "😂", "😍", "😢", "👍",
            "🙏", "👏", "🔥", "💯", "💖",
            "🥰", "🤔", "😎", "🙄", "😉",
            "🎉", "🤗", "😴", "🤯", "🥳"
        ]

        for i, emoji in enumerate(emojis):
            button = tk.Button(emoji_window, text=emoji, font=('Arial', 14), command=lambda e=emoji: self.insert_emoji(e), bg='#3E3E3E', fg='#FFFFFF')
            button.grid(row=i // 5, column=i % 5, padx=5, pady=5, ipadx=10, ipady=10)

    def insert_emoji(self, emoji):
        # insert the users selected emoji into the message entry field
        current_text = self.message_entry.get()
        self.message_entry.delete(0, tk.END)
        self.message_entry.insert(tk.END, current_text + emoji)

    def on_closing(self):
        # ask user for confirmation before closing the application
        if messagebox.askokcancel("Quit", "Do you want to quit the chat?"):
            self.send_system_message(f"{self.username} has left the chat.")
            self.root.destroy()
            self.connection.close()

"""
Start of Functions for the Main GUI, Login Window and Registration Window - formatting for Titles, Colours, Frames, Buttons and Size
"""

def show_main_window():
    global main_window

    main_window = tk.Tk()
    main_window.title("PBT205 Chat Application")
    main_window.configure(bg='#2E2E2E')

    # add the torrens logo image to the top of the window
    logo_path = 'Desktop/University/Tri 2 2024/Project Based Learning Studio/Assessment 3/TorrensLogo.png'
    image = Image.open(logo_path)
    image = image.resize((150, 50), resample=Image.Resampling.BICUBIC)
    logo_image = ImageTk.PhotoImage(image)

    logo_label = tk.Label(main_window, image=logo_image, bg='#2E2E2E')
    logo_label.image = logo_image  # keep a reference to the image
    logo_label.pack(pady=(5, 5))

    title_label = tk.Label(main_window, text="PBT205 Chat Application", bg='#2E2E2E', fg='#FFFFFF', font=('Arial', 24, 'bold'))
    title_label.pack(pady=10)

    button_frame = tk.Frame(main_window, bg='#2E2E2E')
    button_frame.pack(pady=10)

    login_button = tk.Button(button_frame, text="Login", command=show_login_window, bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 16))
    login_button.pack(side=tk.LEFT, padx=(0, 10))

    register_button = tk.Button(button_frame, text="Register", command=show_register_window, bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 16))
    register_button.pack(side=tk.LEFT, padx=(10, 0))

    creator_label = tk.Label(main_window, text="Created by Joshua Gibson A00108030", bg='#2E2E2E', fg='#888888', font=('Arial', 10))
    creator_label.pack(side=tk.BOTTOM, pady=20)

    main_window.mainloop()

def show_login_window():
    global login_window, username_entry, password_entry

    login_window = tk.Toplevel(main_window)
    login_window.title("Login")
    login_window.configure(bg='#2E2E2E')
    login_window.geometry('300x215+400+300')

    username_label = tk.Label(login_window, text="Username", bg='#2E2E2E', fg='#FFFFFF', font=('Arial', 12))
    username_label.pack(pady=(20, 5))

    username_entry = tk.Entry(login_window, bg='#1E1E1E', fg='#FFFFFF', insertbackground='#FFFFFF', font=('Arial', 12))
    username_entry.pack(pady=5)

    password_label = tk.Label(login_window, text="Password", bg='#2E2E2E', fg='#FFFFFF', font=('Arial', 12))
    password_label.pack(pady=(10, 5))

    password_entry = tk.Entry(login_window, show="*", bg='#1E1E1E', fg='#FFFFFF', insertbackground='#FFFFFF', font=('Arial', 12))
    password_entry.pack(pady=5)

    login_button = tk.Button(login_window, text="Login", command=check_login, bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 12))
    login_button.pack(pady=(20, 10))

def show_register_window():
    global register_window, username_entry, password_entry

    register_window = tk.Toplevel(main_window)
    register_window.title("Register")
    register_window.configure(bg='#2E2E2E')
    register_window.geometry('300x215+400+300')

    username_label = tk.Label(register_window, text="Username", bg='#2E2E2E', fg='#FFFFFF', font=('Arial', 12))
    username_label.pack(pady=(20, 5))

    username_entry = tk.Entry(register_window, bg='#1E1E1E', fg='#FFFFFF', insertbackground='#FFFFFF', font=('Arial', 12))
    username_entry.pack(pady=5)

    password_label = tk.Label(register_window, text="Password", bg='#2E2E2E', fg='#FFFFFF', font=('Arial', 12))
    password_label.pack(pady=(10, 5))

    password_entry = tk.Entry(register_window, show="*", bg='#1E1E1E', fg='#FFFFFF', insertbackground='#FFFFFF', font=('Arial', 12))
    password_entry.pack(pady=5)

    register_button = tk.Button(register_window, text="Register", command=register_user, bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 12))
    register_button.pack(pady=(20, 10))

def show_room_window(username):
    global room_window, room_entry

    room_window = tk.Toplevel(main_window)
    room_window.title("Select Room")
    room_window.configure(bg='#2E2E2E')
    room_window.geometry('300x150+400+300')

    room_label = tk.Label(room_window, text="Room Number", bg='#2E2E2E', fg='#FFFFFF', font=('Arial', 12))
    room_label.pack(pady=(20, 5))

    room_entry = tk.Entry(room_window, bg='#1E1E1E', fg='#FFFFFF', insertbackground='#FFFFFF', font=('Arial', 12))
    room_entry.pack(pady=5)

    enter_button = tk.Button(room_window, text="Enter", command=lambda: start_chat(username, room_entry.get()), bg='#3E3E3E', fg='#FFFFFF', font=('Arial', 12))
    enter_button.pack(pady=(20, 10))

"""
End of Functions for the Main GUI, Login Window and Registration Window - formatting for Titles, Colours, Frames, Buttons and Size
"""
# function to start the chat by destroying the room and main windows
def start_chat(username, room):
    room_window.destroy()
    main_window.destroy()
    ChatClient(username, room)

# function to register a user
def register_user():
    username = username_entry.get()
    password = password_entry.get()

    if not username or not password:
        messagebox.showerror("Error", "Please enter a username and password.")
        return

    # hash the password before storing it
    hashed_password = hash_password(password)

    conn = sqlite3.connect('chat_users.db')
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        messagebox.showinfo("Success", "Registration successful!")
        register_window.destroy()
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "Username already exists.")
    finally:
        conn.close()

# function to check a users login     
def check_login():
    username = username_entry.get()
    password = password_entry.get()

    if not username or not password:
        messagebox.showerror("Error", "Please enter a username and password.")
        return

    # hash the password before checking it
    hashed_password = hash_password(password)

    conn = sqlite3.connect('chat_users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()

    if result and result[0] == hashed_password:
        messagebox.showinfo("Success", "Login successful!")
        login_window.destroy()
        show_room_window(username)  # show the room selection window after successful login
    else:
        messagebox.showerror("Error", "Invalid username or password.")

# main program starting point
if __name__ == "__main__":
    show_main_window()