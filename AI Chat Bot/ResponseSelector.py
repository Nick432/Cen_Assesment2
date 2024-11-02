# AI model found at:
# sentence-transformers/all-MiniLM-L6-v2 · Hugging Face. (n.d.). 
# Huggingface.co. 
# https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

# Sentence_transformers code adapted from:
# Quickstart — Sentence Transformers documentation. (2024). 
# Sbert.net. 
# https://sbert.net/docs/quickstart.html


from sentence_transformers import SentenceTransformer, util
import torch
import os
import tkinter as tk
from tkinter import scrolledtext

class ResponseSelector:
    def __init__(self):
        self.Model = SentenceTransformer('all-MiniLM-L6-v2')
        self.Responses = []
        self.ResponseEmbeddings = None

    def LoadResponses(self, FileName):
        self.Responses = []
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, FileName)
            with open(file_path, 'r', encoding='utf-8') as File:
                for Line in File:
                    Line = Line.strip()
                    if Line and not Line.startswith('#'):
                        self.Responses.append(Line)
            print(f"Loaded {len(self.Responses)} responses from {FileName}.")
            self.ResponseEmbeddings = self.Model.encode(self.Responses, convert_to_tensor=True)
        except FileNotFoundError:
            print(f"Error: The file '{FileName}' was not found.")
        except Exception as e:
            print(f"An error occurred while loading responses: {e}")

    def GetResponse(self, UserQuery):
        if not self.Responses:
            return "No responses loaded."

        QueryEmbedding = self.Model.encode(UserQuery, convert_to_tensor=True)
        CosineScores = util.pytorch_cos_sim(QueryEmbedding, self.ResponseEmbeddings)[0]
        TopResult = torch.argmax(CosineScores).item()
        return self.Responses[TopResult]


def create_tkinter_interface():
    selector = ResponseSelector()
    selector.LoadResponses("Responses.txt")

    def get_response(event=None):
        user_query = entry.get()
        if user_query:
            chat_display.config(state=tk.NORMAL)
            chat_display.insert(tk.END, f"Guest: {user_query}\n", "guest")
            entry.delete(0, tk.END)

            response = selector.GetResponse(user_query)
            chat_display.insert(tk.END, f"Robot: {response}\n", "robot")
            chat_display.config(state=tk.DISABLED)
            chat_display.yview(tk.END)

    root = tk.Tk()
    root.title("Response Selector Chat")
    root.geometry("700x500")
    root.configure(bg="#1c1c1c")

    chat_display = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=25, width=70, state=tk.DISABLED, bg="#2b2b2b", fg="white", font=("Arial", 12))
    chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    
    chat_display.tag_config("guest", foreground="white")
    chat_display.tag_config("robot", foreground="white")
    
    chat_display.config(state=tk.NORMAL)
    chat_display.insert(tk.END, "Robot: Hello! How can I assist you today?\n", "robot")
    chat_display.config(state=tk.DISABLED)

    bottom_frame = tk.Frame(root, bg="#1c1c1c")
    bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)

    entry = tk.Entry(bottom_frame, width=60, bg="#333333", fg="white", font=("Arial", 12), insertbackground="white")
    entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
    entry.bind("<Return>", get_response)

    send_button = tk.Button(bottom_frame, text="Send →", command=get_response, bg="#3a3a3a", fg="white", font=("Arial", 12), width=8)
    send_button.pack(side=tk.RIGHT)

    root.mainloop()

create_tkinter_interface()
