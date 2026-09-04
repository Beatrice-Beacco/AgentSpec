from antlr4 import *
import unittest
from enum import Enum
from pydantic import BaseModel 
from spec_lang.AgentSpecListener import AgentSpecListener 
from spec_lang.AgentSpecLexer import AgentSpecLexer
from spec_lang.AgentSpecParser import AgentSpecParser  

class RuleParser(AgentSpecListener): 
   
    event: str
    
    def enterTriggerClause(self, ctx):
        self.event = ctx.event().getText()
         
    def enterRuleClause(self, ctx):
        self.id = ctx.IDENTIFIER(). getText()
             
    def getId(self):
        return self.id

class Rule(BaseModel):
    id: str
    event: str 
    raw: str
     
    def triggered(self, action_name, input:str):  
        # FIX (local): `input` is None for AgentFinish actions and a dict for
        # structured tool inputs; the original unconditionally called .strip()
        # on it, so any normal task completion crashed with AttributeError
        # whenever a tool-triggered rule was loaded.
        if self.event == "any" or action_name == self.event:
            return True
        if input is None:
            return False
        return str(input).strip().startswith(self.event.replace("_",' '))
    
    def trigger_finished(self):
        return self.event=="finish"
    
    def from_text(rule_str):
        input_stream = InputStream(rule_str)
        lexer = AgentSpecLexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        parser = AgentSpecParser(token_stream)

        tree = parser.program()
        walker = ParseTreeWalker()
        rule_parser = RuleParser()
        walker.walk(rule_parser, tree)   
        return Rule(raw=rule_str, event=rule_parser.event, id=rule_parser.getId())
 