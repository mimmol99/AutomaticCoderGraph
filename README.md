# AutomaticCoder
Automatic Coder Writer/Rewiever Using LLM and LangGraph.

![alt_text](https://github.com/mimmol99/AutomaticCoder/blob/main/graph.png?raw=True)

# Working logic
Write a request.

The model initially write the python code to solve the request.
(or pass directly the code)

- The reviewer write a feedback about the code.
- the coder re-write the code using the feedback.
- The new code is run by executor.
- Errors are eventually fixed or missing packages are installed.
- Return to the reviewer and repeat all cycle until max iterations is reached.
   
# Usage

Write your API_KEY in an env file.

install requirements

```python 
pip install -r requirements.txt
```

run main

```python 
python3 main.py
```

