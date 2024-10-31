import ResponseSelector

Selector = ResponseSelector.ResponseSelector()
Selector.LoadResponses("Responses.txt")

while True:
    UserInput = input("Message: ").strip()
    Response = Selector.GetResponse(UserInput)
    print(f"Response: {Response}\n")