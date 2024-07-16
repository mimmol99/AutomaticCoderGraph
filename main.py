import os
from dotenv import load_dotenv
from typing import Dict, TypedDict, Optional,Type,Any
from openai import OpenAI
import langgraph.graph
from langgraph.graph import Graph, StateGraph, END
from langchain_core.runnables.graph_png import PngDrawer
import subprocess
import sys
import inspect


def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return None
    except Exception as e:
        return(str(e))

load_dotenv('../api_key.env')



client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

def print_actual_func():
    print(f"Running node  {str(inspect.currentframe().f_back.f_code.co_name)} ")


def generate_conversation(prompt: str) -> str:
    chat_completion = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': prompt}],
    )
    response = chat_completion.choices[0].message.content
    return response

reviewer_start = "You are Code reviewer specialized in {}. \
You need to review the given code following PEP8 guidelines and potential bugs \
and point out issues as bullet list. \
Code:\n{}"

coder_start = "You are a Coder specialized in {}. \
Improve the given code given the following guidelines. Guideline:\n{} \n \
Code:\n{} \n \
Output just the improved code and nothing else (don't output '''python or similar)."

rating_start = "Rate the skills of the coder on a scale of 10 given the Code review cycle with a short reason. \
Code review:\n{} \n"

code_comparison = "Compare the two code snippets and rate on a scale of 10 to both. Don't output the codes. Revised Code:\n{} \n Actual Code:\n{}"

classify_feedback = "Are all feedback mentioned resolved in the code? Output just Yes or No. \
Code:\n{} \n Feedback:\n{} \n"

classify_errors = "You are a errors classifier. If the error passed is about \
a module or package to be installed, return the list of packages that must be installed \
using pip(e.g. '[torch, transformers]'), else return an empty list (e.g. '[]'). Error: {}"

error_fix_prompt = "You are a skilled programmer. Fix the following errors in the code:\nError:\n{} \nCode:\n{} \nOutput just the fixed code and nothing else (don't output '''python or similar)."

error_fix_package = "I just tried to install {} using subprocess.check_call([sys.executable, '-m', 'pip', 'install', {}]),but it returns this error: {} return only the correct package name "

class GraphState(TypedDict):
    actual_code: Optional[str]
    code: Optional[str]
    code_compare: Optional[str]
    feedback: Optional[str]
    history: Optional[str]
    iterations: Optional[int]
    rating: Optional[str]
    specialization: Optional[str]
    error: Optional[str]

class StateGraph(Graph):

    def __init__(self, schema: Type[Any]) -> None:

        super().__init__()
        # Here
        #if any(isinstance(c, BinaryOperatorAggregate) for c in self.channels.values()): 
        self.support_multiple_edges = True
        


workflow = StateGraph(GraphState)

def handle_reviewer(state: Dict) -> Dict:
    print_actual_func()
    history = state.get('history', '').strip()
    code = state.get('code', '').strip()
    specialization = state.get('specialization', '').strip()
    iterations = state.get('iterations')
    feedback = generate_conversation(reviewer_start.format(specialization, code))
    state.update({'history': history + "\n REVIEWER:\n" + feedback, 'feedback': feedback, 'iterations': iterations + 1})
    return state

def handle_coder(state: Dict) -> Dict:
    print_actual_func()
    history = state.get('history', '').strip()
    feedback = state.get('feedback', '').strip()
    code_input = state.get('code', '').strip()
    specialization = state.get('specialization', '').strip()
    code = generate_conversation(coder_start.format(specialization, feedback, code_input))
    state.update({'history': history + '\n CODER:\n' + code, 'code': code})
    return state

def handle_executor(state: Dict) -> Dict:
    print_actual_func()
    code_input = state.get('code', '').strip()
    error_output = None
    try:
        output = exec(code)
    except Exception as e:
        print(f"Found error:",e)
        error_output = str(e)
    state.update({'error':error_output})
    return state

def handle_error(state: Dict) -> Dict:
    print_actual_func()
    error = state.get('error', None)
    if error is None: return state 
    code_input = state.get('code', '').strip()
    new_code = generate_conversation(error_fix_prompt.format(error, code_input))
    state.update({'code': new_code, 'error': None})
    return state

def handle_installing_package(state: Dict) -> Dict:
    print_actual_func()
    error = state.get('error', None)
    if error is None: return state 
    packages_to_install = generate_conversation(classify_errors.format(error))
    packages_to_install = eval(packages_to_install.replace("'", " ").replace("`"," "))
    #packages_to_install = packages_to_install.replace("'", " ").replace("`"," ").split(",")
    #print(packages_to_install)
    for package in packages_to_install:
        error = install(package)
        print(f"installed {package}")
        if error is not None:
            new_package = generate_conversation(error_fix_package.format(package,package,error))
            new_error = install(new_package)
        print(f"installed {package}")

    state.update({'error': None})
    return state

def handle_result(state: Dict) -> Dict:
    print_actual_func()
    history = state['history']
    code1 = state['code']
    code2 = state['actual_code']
    rating = generate_conversation(rating_start.format(history))
    code_compare = generate_conversation(code_comparison.format(code1, code2))
    state.update({'rating': rating, 'code_compare': code_compare})
    return state

workflow.add_node('handle_reviewer', handle_reviewer)
workflow.add_node('handle_coder', handle_coder)
workflow.add_node('handle_executor', handle_executor)
workflow.add_node('handle_error', handle_error)
workflow.add_node('handle_installing_package', handle_installing_package)
workflow.add_node('handle_result', handle_result)

def check_deployment(state: Dict) -> str:
    deployment_ready = 1 if 'yes' in generate_conversation(classify_feedback.format(state.get('code'), state.get('feedback'))).lower() else 0
    total_iterations = 1 if state.get('iterations', 0) > 5 else 0
    next_state = 'handle_result' if deployment_ready or total_iterations else 'handle_coder'
    return next_state

def check_error(state: Dict) -> str:
    error_present =  state.get('error', None)
    next_state = 'handle_reviewer'
    if error_present is not None:
        if 'No module named' in state['error']:
            next_state = 'handle_installing_package'
        else:
            next_state = 'handle_error'
    return next_state

workflow.add_conditional_edges(
    'handle_reviewer',
    check_deployment,
    {
        "handle_coder": "handle_coder",
        "handle_result": "handle_result",
    }
)

"""
workflow.add_conditional_edges(
    'handle_coder',
    lambda state: 'handle_executor',
    {
        "handle_executor":"handle_executor"
    }
)
"""

workflow.add_conditional_edges(
    'handle_executor',
    check_error,
    {
        "handle_error": "handle_error",
        "handle_installing_package": "handle_installing_package",
        "handle_reviewer": "handle_reviewer"
    }
)


workflow.set_entry_point('handle_reviewer')
#workflow.add_edge('handle_coder', 'handle_reviewer')
workflow.add_edge('handle_coder', 'handle_executor')
#workflow.add_edge('handle_executor', 'handle_error')
#workflow.add_edge('handle_executor', 'handle_installing_package')
workflow.add_edge('handle_error','handle_reviewer')
workflow.add_edge('handle_installing_package', 'handle_reviewer')
workflow.add_edge('handle_result', langgraph.graph.END)

specialization = 'python'

problem = 'Generate the complete python code to create a distillation model (from an openai model to an opensourced one) and test both model on LLM benchmarks. The code must be ready to be run to do all steps.'
file_name = generate_conversation(f"Output just a 'file_name.py' that well represents this problem: {problem}. The output will be used as the name of a python file.")
code = generate_conversation(problem)

app = workflow.compile()
conversation = app.invoke({"history": code, "code": code, 'actual_code': code, "specialization": specialization, 'iterations': 0,'error':None})

#print(conversation['code_compare'])

new_code = conversation["code"]
#print("Actual code", code, "\n\n\n New code:", new_code)

with open(file_name, 'w') as f:
    f.write(new_code)

pngdrawer = PngDrawer()
pngdrawer.draw(app.get_graph(), f"./{sys.argv[0]}_graph.png")
