import unittest
import os
from antlr4 import *
from .AgentSpecLexer import AgentSpecLexer
from .AgentSpecParser import AgentSpecParser
from antlr4.error.ErrorListener import ErrorListener

class CustomErrorListener(ErrorListener): 
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ValueError( f"Syntax error at line {line}, column {column}: {msg}") 
 
def parse(program):
    # Expected parse tree (this should match your grammar's expectations) 

    # Create a lexer and parser
    input_stream = InputStream(program)
    lexer = AgentSpecLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = AgentSpecParser(token_stream)

    error_listener = CustomErrorListener()
    parser.removeErrorListeners()  # Remove default ConsoleErrorListener
    parser.addErrorListener(error_listener)

    # Parse the input using the top-level rule (e.g., `program`) 
    tree = parser.program()
    # Print the parse tree
    print(tree.toStringTree(recog=parser))
 

class TestAgentSpecParser(unittest.TestCase):

    def test_grammar_examples(self):
        # FIX (local): `base` was the relative string 'rule_examples/', so this
        # test could only run with the cwd set to src/spec_lang -- from anywhere
        # else it died with FileNotFoundError before parsing anything. Resolve
        # it against this file instead.
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'rule_examples')
        # Only .ar files in this directory: `legacy/` holds the pre-grammar
        # originals, which do not parse on purpose (see its README).
        names = sorted(f for f in os.listdir(base) if f.endswith('.ar'))
        assert names, f'no fixtures in {base}'
        for f in names:
            with open(os.path.join(base, f), 'r') as r:
                try:
                    rule = r.read()
                    parse(rule)
                except ValueError as e:
                    assert False, f'{f}: {e}' 

if __name__ == "__main__":
    unittest.main()

# def main():
#     # Get input for testing
#     input_text = """
#     rule @inspect_dangerous_command_before_execution
#     trigger 
#         act TerminalExecute  
#     check 
#         llm_judge(cur_action["command"], "Return true if it is risky command, [description of risky command]")
#     enforce 
#         user_inspection
#     end
#     """

#     # Create a lexer and parser
#     input_stream = InputStream(input_text)
#     lexer = AgentSpecLexer(input_stream)
#     token_stream = CommonTokenStream(lexer)
#     parser = AgentSpecParser(token_stream)

#     # Parse the input using the top-level rule (e.g., program)
#     tree = parser.program()

#     # Print the parse tree
#     print(tree.toStringTree(recog=parser))

# if __name__ == "__main__":
#     main()