# AutomaticCoder
Automatic Coder Writer/Rewiever Using LLM and LangGraph.

Write a request.

- The model write the python code to solve the request
- The reviewer check if the code is well-written and there are possible fixings/improvements
- The code is run
- Errors are eventually fixed or missing packages are installed
- Return to the rewier and repeat until max iterations is reached
   
#Usage

```python 
pip install -r requirements.txt
```
```python 
python3 main.py
```

