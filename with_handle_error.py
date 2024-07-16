import os
from dotenv import load_dotenv
from typing import Dict, TypedDict, Optional
from openai import OpenAI
import langgraph.graph
from langchain_core.runnables.graph_png import PngDrawer
import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

load_dotenv('../api_key.env')

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)


def generate_conversation(prompt: str) -> str:
    chat_completion = client.chat.completions.create(
        model='gpt-4-turbo',
        messages=[{'role': 'user', 'content': prompt}],
    )
    response = chat_completion.choices[0].message.content
    return response

file_name = "distillation.py"

reviewer_start = "You are Code reviewer specialized in {}. \
You need to review the given code following PEP8 guidelines and potential bugs \
and point out issues as bullet list. \
Code:\n{}"

coder_start = "You are a Coder specialized in {}. \
Improve the given code given the following guidelines. Guideline:\n{} \n \
Code:\n{} \n \
Output just the improved code and nothing else (dont' output '''python or similar)."

rating_start = "Rate the skills of the coder on a scale of 10 given the Code review cycle with a short reason. \
Code review:\n{} \n"

code_comparison = "Compare the two code snippets and rate on a scale of 10 to both. Don't output the codes. Revised Code:\n{} \n Actual Code:\n{}"

classify_feedback = "Are all feedback mentioned resolved in the code? Output just Yes or No. \
Code:\n{} \n Feedback:\n{} \n"

classify_errors = "You are a errors classifier. If the error passed is about \
a module or package to be installed,return the list of packages that must be installed \
using pip(e.g. '[torch,transformers]'),else return an empty list (e.g. '[]'). Error: {}"

error_fix_prompt = "You are a skilled programmer. Fix the following errors in the code:\nError:\n{} \nCode:\n{} \n.Output just the fixed code and nothing else(dont' output '''python or similar)."

class GraphState(TypedDict):
    actual_code: Optional[str] = None
    code: Optional[str] = None
    code_compare: Optional[str] = None
    feedback: Optional[str] = None
    history: Optional[str] = None
    iterations: Optional[int] = None
    rating: Optional[str] = None
    specialization: Optional[str] = None
    new_file_name: Optional[str] = None  # Added new_file_name
    error: Optional[str] = None  # Added error field

workflow = langgraph.graph.StateGraph(GraphState)

def handle_reviewer(state: Dict) -> Dict:
    history = state.get('history', '').strip()
    code = state.get('code', '').strip()
    specialization = state.get('specialization', '').strip()
    iterations = state.get('iterations')
    
    feedback = generate_conversation(reviewer_start.format(specialization, code))
    #print(f"Feedback:",generate_conversation("Summarize this feedback in few words :"+feedback) )
    return {'history': history + "\n REVIEWER:\n" + feedback, 'feedback': feedback, 'iterations': iterations + 1}

def handle_coder(state: Dict) -> Dict:
    history = state.get('history', '').strip()
    feedback = state.get('feedback', '').strip()
    code_input = state.get('code', '').strip()
    specialization = state.get('specialization', '').strip()
    
    code = generate_conversation(coder_start.format(specialization, feedback, code_input))
    print("Rewriting code..")
    state.update({'history': history + '\n CODER:\n' + code, 'code': code})

    # Save the new code to the file
    new_file_name = state.get('new_file_name', file_name)
    with open(new_file_name, 'w') as file:
        file.write(code)
    
    return state

def check_code_errors(code):
    error_output = None
    try:
        output = exec(code)
    except Exception as e:
        print(f"Found error:",e)
        error_output = str(e)
    return error_output

def handle_error(state: Dict) -> Dict:
    new_file_name = state.get('new_file_name', file_name)
    code = state.get('code', '').strip()
    error_output = check_code_errors(code)

    while error_output is not None:
        print(f"error output:{error_output}")
        fixed_code = generate_conversation(error_fix_prompt.format(error_output, code))
        error_output = check_code_errors(fixed_code)
        error_class = generate_conversation(classify_errors.format(error_output))
        
        error_class_list = error_class.replace("[", "").replace("]", "").replace("'", "").split(",")

        #error_class_list = list(error_class.replace("'", ""))

        for package in error_class_list:
            install(package)

        print(error_output,error_class)
        if error_output is not None:
            state.update({'history': state.get('history', '') + "\n ERROR:\n" + error_output, 'code': fixed_code, 'error': ''})
        else:
            state.update({'history': state.get('history', ''), 'code': fixed_code, 'error': ''})

    return state

def handle_result(state: Dict) -> Dict:
    history = state.get('history', '').strip()
    code1 = state.get('code', '').strip()
    code2 = state.get('actual_code', '').strip()
    rating = generate_conversation(rating_start.format(history))
    
    code_compare = generate_conversation(code_comparison.format(code1, code2))
    return {'rating': rating, 'code_compare': code_compare}

workflow.add_node('handle_reviewer', handle_reviewer)
workflow.add_node('handle_coder', handle_coder)
workflow.add_node('handle_result', handle_result)
workflow.add_node('handle_error', handle_error)  # Added handle_error node

def check_deployment(state: Dict) -> str:
    deployment_ready = 1 if 'yes' in generate_conversation(classify_feedback.format(state.get('code'), state.get('feedback'))).lower() else 0
    total_iterations = 1 if state.get('iterations', 0) > 5 else 0
    error_present = 1 if state.get('error', None)!= None else 0
    if error_present:
        return 'handle_error'
    return 'handle_result' if deployment_ready or total_iterations else 'handle_coder'

workflow.add_conditional_edges(
    'handle_reviewer',
    check_deployment
)

workflow.set_entry_point('handle_reviewer')
workflow.add_edge('handle_coder', 'handle_reviewer')
workflow.add_edge('handle_reviewer', 'handle_error') 
workflow.add_edge('handle_result', langgraph.graph.END)

specialization = 'python'

problem = 'Generate the complete python code to create a distillation model (from an openai model to an opensourced one) and test both model on LLM benchmarks. The code must be ready to be run to do all steps.'
code = generate_conversation(problem)

#code = open('./main.py', 'r').read()

app = workflow.compile()
conversation = app.invoke({"history": code, "code": code, 'actual_code': code, "specialization": specialization, 'iterations': 0, 'new_file_name': file_name})

print(conversation['code_compare'])

new_code = conversation['code']
print("Actual code", code, "\n\n\n New code:", new_code)

open('distillation.py', 'w').write(new_code)

pngdrawer = PngDrawer()
pngdrawer.draw(app.get_graph(),"./with_error.png")

