# Generated from agentguard/speclang/AgentSpecFull.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,35,180,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,1,0,5,0,40,8,0,
        10,0,12,0,43,9,0,1,0,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,2,1,2,1,2,1,2,
        1,3,1,3,1,3,1,4,1,4,1,4,5,4,63,8,4,10,4,12,4,66,9,4,1,5,4,5,69,8,
        5,11,5,12,5,70,1,6,1,6,1,6,5,6,76,8,6,10,6,12,6,79,9,6,1,7,1,7,1,
        8,1,8,1,8,3,8,86,8,8,1,8,5,8,89,8,8,10,8,12,8,92,9,8,1,9,1,9,4,9,
        96,8,9,11,9,12,9,97,1,10,1,10,1,10,1,10,1,10,1,10,3,10,106,8,10,
        1,11,1,11,1,11,1,11,1,11,5,11,113,8,11,10,11,12,11,116,9,11,1,11,
        1,11,1,12,1,12,1,12,1,12,3,12,124,8,12,1,12,1,12,3,12,128,8,12,1,
        13,1,13,1,13,1,13,1,13,1,13,1,13,1,13,5,13,138,8,13,10,13,12,13,
        141,9,13,1,13,1,13,1,13,1,14,1,14,1,14,1,14,1,15,1,15,1,15,1,15,
        1,15,3,15,155,8,15,1,15,1,15,1,15,1,15,5,15,161,8,15,10,15,12,15,
        164,9,15,1,16,1,16,1,17,4,17,169,8,17,11,17,12,17,170,1,17,1,17,
        1,17,1,17,1,18,1,18,1,18,1,18,0,1,30,19,0,2,4,6,8,10,12,14,16,18,
        20,22,24,26,28,30,32,34,36,0,2,2,0,5,5,25,29,1,0,31,32,181,0,41,
        1,0,0,0,2,46,1,0,0,0,4,52,1,0,0,0,6,56,1,0,0,0,8,59,1,0,0,0,10,68,
        1,0,0,0,12,72,1,0,0,0,14,80,1,0,0,0,16,82,1,0,0,0,18,93,1,0,0,0,
        20,105,1,0,0,0,22,107,1,0,0,0,24,127,1,0,0,0,26,129,1,0,0,0,28,145,
        1,0,0,0,30,154,1,0,0,0,32,165,1,0,0,0,34,168,1,0,0,0,36,176,1,0,
        0,0,38,40,3,2,1,0,39,38,1,0,0,0,40,43,1,0,0,0,41,39,1,0,0,0,41,42,
        1,0,0,0,42,44,1,0,0,0,43,41,1,0,0,0,44,45,5,0,0,1,45,1,1,0,0,0,46,
        47,3,4,2,0,47,48,3,6,3,0,48,49,3,16,8,0,49,50,3,18,9,0,50,51,5,8,
        0,0,51,3,1,0,0,0,52,53,5,1,0,0,53,54,5,18,0,0,54,55,5,29,0,0,55,
        5,1,0,0,0,56,57,5,2,0,0,57,58,3,8,4,0,58,7,1,0,0,0,59,64,3,10,5,
        0,60,61,5,22,0,0,61,63,3,10,5,0,62,60,1,0,0,0,63,66,1,0,0,0,64,62,
        1,0,0,0,64,65,1,0,0,0,65,9,1,0,0,0,66,64,1,0,0,0,67,69,3,12,6,0,
        68,67,1,0,0,0,69,70,1,0,0,0,70,68,1,0,0,0,70,71,1,0,0,0,71,11,1,
        0,0,0,72,77,3,14,7,0,73,74,5,15,0,0,74,76,3,14,7,0,75,73,1,0,0,0,
        76,79,1,0,0,0,77,75,1,0,0,0,77,78,1,0,0,0,78,13,1,0,0,0,79,77,1,
        0,0,0,80,81,7,0,0,0,81,15,1,0,0,0,82,83,5,3,0,0,83,90,3,20,10,0,
        84,86,5,21,0,0,85,84,1,0,0,0,85,86,1,0,0,0,86,87,1,0,0,0,87,89,3,
        20,10,0,88,85,1,0,0,0,89,92,1,0,0,0,90,88,1,0,0,0,90,91,1,0,0,0,
        91,17,1,0,0,0,92,90,1,0,0,0,93,95,5,4,0,0,94,96,3,24,12,0,95,94,
        1,0,0,0,96,97,1,0,0,0,97,95,1,0,0,0,97,98,1,0,0,0,98,19,1,0,0,0,
        99,106,5,6,0,0,100,106,5,7,0,0,101,102,5,20,0,0,102,106,3,20,10,
        0,103,106,3,22,11,0,104,106,5,29,0,0,105,99,1,0,0,0,105,100,1,0,
        0,0,105,101,1,0,0,0,105,103,1,0,0,0,105,104,1,0,0,0,106,21,1,0,0,
        0,107,108,5,29,0,0,108,109,5,11,0,0,109,114,3,32,16,0,110,111,5,
        10,0,0,111,113,3,32,16,0,112,110,1,0,0,0,113,116,1,0,0,0,114,112,
        1,0,0,0,114,115,1,0,0,0,115,117,1,0,0,0,116,114,1,0,0,0,117,118,
        5,12,0,0,118,23,1,0,0,0,119,123,5,24,0,0,120,121,5,11,0,0,121,122,
        5,30,0,0,122,124,5,12,0,0,123,120,1,0,0,0,123,124,1,0,0,0,124,128,
        1,0,0,0,125,128,3,26,13,0,126,128,3,34,17,0,127,119,1,0,0,0,127,
        125,1,0,0,0,127,126,1,0,0,0,128,25,1,0,0,0,129,130,5,23,0,0,130,
        131,5,11,0,0,131,132,5,29,0,0,132,133,5,10,0,0,133,134,5,13,0,0,
        134,139,3,28,14,0,135,136,5,10,0,0,136,138,3,28,14,0,137,135,1,0,
        0,0,138,141,1,0,0,0,139,137,1,0,0,0,139,140,1,0,0,0,140,142,1,0,
        0,0,141,139,1,0,0,0,142,143,5,14,0,0,143,144,5,12,0,0,144,27,1,0,
        0,0,145,146,5,30,0,0,146,147,5,9,0,0,147,148,3,30,15,0,148,29,1,
        0,0,0,149,150,6,15,-1,0,150,155,5,30,0,0,151,155,3,32,16,0,152,155,
        5,29,0,0,153,155,3,26,13,0,154,149,1,0,0,0,154,151,1,0,0,0,154,152,
        1,0,0,0,154,153,1,0,0,0,155,162,1,0,0,0,156,157,10,2,0,0,157,158,
        5,16,0,0,158,159,5,30,0,0,159,161,5,17,0,0,160,156,1,0,0,0,161,164,
        1,0,0,0,162,160,1,0,0,0,162,163,1,0,0,0,163,31,1,0,0,0,164,162,1,
        0,0,0,165,166,7,1,0,0,166,33,1,0,0,0,167,169,3,36,18,0,168,167,1,
        0,0,0,169,170,1,0,0,0,170,168,1,0,0,0,170,171,1,0,0,0,171,172,1,
        0,0,0,172,173,5,29,0,0,173,174,5,19,0,0,174,175,3,32,16,0,175,35,
        1,0,0,0,176,177,5,29,0,0,177,178,5,9,0,0,178,37,1,0,0,0,15,41,64,
        70,77,85,90,97,105,114,123,127,139,154,162,170
    ]

class AgentSpecFullParser ( Parser ):

    grammarFileName = "AgentSpecFull.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'rule'", "'trigger'", "'check'", "'enforce'", 
                     "'any'", "<INVALID>", "<INVALID>", "'end'", "':'", 
                     "','", "'('", "')'", "'{'", "'}'", "'.'", "'['", "']'", 
                     "'@'", "'='", "'!'", "'&'", "'|'", "'invoke_action'", 
                     "<INVALID>", "'state_change'", "'before_action'", "'after_action'", 
                     "'finish'" ]

    symbolicNames = [ "<INVALID>", "RULE", "TRIGGER", "CHECK", "ENFORCE", 
                      "ANY", "TRUE", "FALSE", "END", "COLON", "COMMA", "LPAREN", 
                      "RPAREN", "LBRACE", "RBRACE", "DOT", "LBRACK", "RBRACK", 
                      "AT", "EQ", "NOT", "AND", "OR", "INVOKE", "ENFORCEMENT", 
                      "STATE_CHANGE", "BEFORE_ACTION", "AFTER_ACTION", "FINISH", 
                      "IDENTIFIER", "STRING", "INTEGER", "FLOAT", "LINE_COMMENT", 
                      "BLOCK_COMMENT", "WS" ]

    RULE_program = 0
    RULE_rule = 1
    RULE_ruleClause = 2
    RULE_triggerClause = 3
    RULE_event = 4
    RULE_eventTerm = 5
    RULE_eventPath = 6
    RULE_eventWord = 7
    RULE_checkClause = 8
    RULE_enforceClause = 9
    RULE_predicate = 10
    RULE_predicateFunc = 11
    RULE_enforcement = 12
    RULE_actionInvoke = 13
    RULE_kvPair = 14
    RULE_value = 15
    RULE_number = 16
    RULE_config = 17
    RULE_namespace = 18

    ruleNames =  [ "program", "rule", "ruleClause", "triggerClause", "event", 
                   "eventTerm", "eventPath", "eventWord", "checkClause", 
                   "enforceClause", "predicate", "predicateFunc", "enforcement", 
                   "actionInvoke", "kvPair", "value", "number", "config", 
                   "namespace" ]

    EOF = Token.EOF
    RULE=1
    TRIGGER=2
    CHECK=3
    ENFORCE=4
    ANY=5
    TRUE=6
    FALSE=7
    END=8
    COLON=9
    COMMA=10
    LPAREN=11
    RPAREN=12
    LBRACE=13
    RBRACE=14
    DOT=15
    LBRACK=16
    RBRACK=17
    AT=18
    EQ=19
    NOT=20
    AND=21
    OR=22
    INVOKE=23
    ENFORCEMENT=24
    STATE_CHANGE=25
    BEFORE_ACTION=26
    AFTER_ACTION=27
    FINISH=28
    IDENTIFIER=29
    STRING=30
    INTEGER=31
    FLOAT=32
    LINE_COMMENT=33
    BLOCK_COMMENT=34
    WS=35

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ProgramContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(AgentSpecFullParser.EOF, 0)

        def rule_(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.RuleContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.RuleContext,i)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_program

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterProgram" ):
                listener.enterProgram(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitProgram" ):
                listener.exitProgram(self)




    def program(self):

        localctx = AgentSpecFullParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 41
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==1:
                self.state = 38
                self.rule_()
                self.state = 43
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 44
            self.match(AgentSpecFullParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RuleContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ruleClause(self):
            return self.getTypedRuleContext(AgentSpecFullParser.RuleClauseContext,0)


        def triggerClause(self):
            return self.getTypedRuleContext(AgentSpecFullParser.TriggerClauseContext,0)


        def checkClause(self):
            return self.getTypedRuleContext(AgentSpecFullParser.CheckClauseContext,0)


        def enforceClause(self):
            return self.getTypedRuleContext(AgentSpecFullParser.EnforceClauseContext,0)


        def END(self):
            return self.getToken(AgentSpecFullParser.END, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_rule

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRule" ):
                listener.enterRule(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRule" ):
                listener.exitRule(self)




    def rule_(self):

        localctx = AgentSpecFullParser.RuleContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_rule)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 46
            self.ruleClause()
            self.state = 47
            self.triggerClause()
            self.state = 48
            self.checkClause()
            self.state = 49
            self.enforceClause()
            self.state = 50
            self.match(AgentSpecFullParser.END)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RuleClauseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def RULE(self):
            return self.getToken(AgentSpecFullParser.RULE, 0)

        def AT(self):
            return self.getToken(AgentSpecFullParser.AT, 0)

        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_ruleClause

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRuleClause" ):
                listener.enterRuleClause(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRuleClause" ):
                listener.exitRuleClause(self)




    def ruleClause(self):

        localctx = AgentSpecFullParser.RuleClauseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_ruleClause)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 52
            self.match(AgentSpecFullParser.RULE)
            self.state = 53
            self.match(AgentSpecFullParser.AT)
            self.state = 54
            self.match(AgentSpecFullParser.IDENTIFIER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TriggerClauseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TRIGGER(self):
            return self.getToken(AgentSpecFullParser.TRIGGER, 0)

        def event(self):
            return self.getTypedRuleContext(AgentSpecFullParser.EventContext,0)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_triggerClause

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTriggerClause" ):
                listener.enterTriggerClause(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTriggerClause" ):
                listener.exitTriggerClause(self)




    def triggerClause(self):

        localctx = AgentSpecFullParser.TriggerClauseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_triggerClause)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 56
            self.match(AgentSpecFullParser.TRIGGER)
            self.state = 57
            self.event()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EventContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def eventTerm(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.EventTermContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.EventTermContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(AgentSpecFullParser.OR)
            else:
                return self.getToken(AgentSpecFullParser.OR, i)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_event

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEvent" ):
                listener.enterEvent(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEvent" ):
                listener.exitEvent(self)




    def event(self):

        localctx = AgentSpecFullParser.EventContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_event)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 59
            self.eventTerm()
            self.state = 64
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==22:
                self.state = 60
                self.match(AgentSpecFullParser.OR)
                self.state = 61
                self.eventTerm()
                self.state = 66
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EventTermContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def eventPath(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.EventPathContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.EventPathContext,i)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_eventTerm

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEventTerm" ):
                listener.enterEventTerm(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEventTerm" ):
                listener.exitEventTerm(self)




    def eventTerm(self):

        localctx = AgentSpecFullParser.EventTermContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_eventTerm)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 68 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 67
                self.eventPath()
                self.state = 70 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 1040187424) != 0)):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EventPathContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def eventWord(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.EventWordContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.EventWordContext,i)


        def DOT(self, i:int=None):
            if i is None:
                return self.getTokens(AgentSpecFullParser.DOT)
            else:
                return self.getToken(AgentSpecFullParser.DOT, i)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_eventPath

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEventPath" ):
                listener.enterEventPath(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEventPath" ):
                listener.exitEventPath(self)




    def eventPath(self):

        localctx = AgentSpecFullParser.EventPathContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_eventPath)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 72
            self.eventWord()
            self.state = 77
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==15:
                self.state = 73
                self.match(AgentSpecFullParser.DOT)
                self.state = 74
                self.eventWord()
                self.state = 79
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EventWordContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def STATE_CHANGE(self):
            return self.getToken(AgentSpecFullParser.STATE_CHANGE, 0)

        def BEFORE_ACTION(self):
            return self.getToken(AgentSpecFullParser.BEFORE_ACTION, 0)

        def AFTER_ACTION(self):
            return self.getToken(AgentSpecFullParser.AFTER_ACTION, 0)

        def FINISH(self):
            return self.getToken(AgentSpecFullParser.FINISH, 0)

        def ANY(self):
            return self.getToken(AgentSpecFullParser.ANY, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_eventWord

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEventWord" ):
                listener.enterEventWord(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEventWord" ):
                listener.exitEventWord(self)




    def eventWord(self):

        localctx = AgentSpecFullParser.EventWordContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_eventWord)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 80
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1040187424) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CheckClauseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CHECK(self):
            return self.getToken(AgentSpecFullParser.CHECK, 0)

        def predicate(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.PredicateContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.PredicateContext,i)


        def AND(self, i:int=None):
            if i is None:
                return self.getTokens(AgentSpecFullParser.AND)
            else:
                return self.getToken(AgentSpecFullParser.AND, i)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_checkClause

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterCheckClause" ):
                listener.enterCheckClause(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitCheckClause" ):
                listener.exitCheckClause(self)




    def checkClause(self):

        localctx = AgentSpecFullParser.CheckClauseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_checkClause)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 82
            self.match(AgentSpecFullParser.CHECK)
            self.state = 83
            self.predicate()
            self.state = 90
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 540016832) != 0):
                self.state = 85
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==21:
                    self.state = 84
                    self.match(AgentSpecFullParser.AND)


                self.state = 87
                self.predicate()
                self.state = 92
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EnforceClauseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ENFORCE(self):
            return self.getToken(AgentSpecFullParser.ENFORCE, 0)

        def enforcement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.EnforcementContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.EnforcementContext,i)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_enforceClause

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEnforceClause" ):
                listener.enterEnforceClause(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEnforceClause" ):
                listener.exitEnforceClause(self)




    def enforceClause(self):

        localctx = AgentSpecFullParser.EnforceClauseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_enforceClause)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 93
            self.match(AgentSpecFullParser.ENFORCE)
            self.state = 95 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 94
                self.enforcement()
                self.state = 97 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 562036736) != 0)):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PredicateContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TRUE(self):
            return self.getToken(AgentSpecFullParser.TRUE, 0)

        def FALSE(self):
            return self.getToken(AgentSpecFullParser.FALSE, 0)

        def NOT(self):
            return self.getToken(AgentSpecFullParser.NOT, 0)

        def predicate(self):
            return self.getTypedRuleContext(AgentSpecFullParser.PredicateContext,0)


        def predicateFunc(self):
            return self.getTypedRuleContext(AgentSpecFullParser.PredicateFuncContext,0)


        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_predicate

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPredicate" ):
                listener.enterPredicate(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPredicate" ):
                listener.exitPredicate(self)




    def predicate(self):

        localctx = AgentSpecFullParser.PredicateContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_predicate)
        try:
            self.state = 105
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,7,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 99
                self.match(AgentSpecFullParser.TRUE)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 100
                self.match(AgentSpecFullParser.FALSE)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 101
                self.match(AgentSpecFullParser.NOT)
                self.state = 102
                self.predicate()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 103
                self.predicateFunc()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 104
                self.match(AgentSpecFullParser.IDENTIFIER)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PredicateFuncContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def LPAREN(self):
            return self.getToken(AgentSpecFullParser.LPAREN, 0)

        def number(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.NumberContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.NumberContext,i)


        def RPAREN(self):
            return self.getToken(AgentSpecFullParser.RPAREN, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(AgentSpecFullParser.COMMA)
            else:
                return self.getToken(AgentSpecFullParser.COMMA, i)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_predicateFunc

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPredicateFunc" ):
                listener.enterPredicateFunc(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPredicateFunc" ):
                listener.exitPredicateFunc(self)




    def predicateFunc(self):

        localctx = AgentSpecFullParser.PredicateFuncContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_predicateFunc)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 107
            self.match(AgentSpecFullParser.IDENTIFIER)
            self.state = 108
            self.match(AgentSpecFullParser.LPAREN)
            self.state = 109
            self.number()
            self.state = 114
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==10:
                self.state = 110
                self.match(AgentSpecFullParser.COMMA)
                self.state = 111
                self.number()
                self.state = 116
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 117
            self.match(AgentSpecFullParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EnforcementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ENFORCEMENT(self):
            return self.getToken(AgentSpecFullParser.ENFORCEMENT, 0)

        def LPAREN(self):
            return self.getToken(AgentSpecFullParser.LPAREN, 0)

        def STRING(self):
            return self.getToken(AgentSpecFullParser.STRING, 0)

        def RPAREN(self):
            return self.getToken(AgentSpecFullParser.RPAREN, 0)

        def actionInvoke(self):
            return self.getTypedRuleContext(AgentSpecFullParser.ActionInvokeContext,0)


        def config(self):
            return self.getTypedRuleContext(AgentSpecFullParser.ConfigContext,0)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_enforcement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEnforcement" ):
                listener.enterEnforcement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEnforcement" ):
                listener.exitEnforcement(self)




    def enforcement(self):

        localctx = AgentSpecFullParser.EnforcementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_enforcement)
        self._la = 0 # Token type
        try:
            self.state = 127
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [24]:
                self.enterOuterAlt(localctx, 1)
                self.state = 119
                self.match(AgentSpecFullParser.ENFORCEMENT)
                self.state = 123
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==11:
                    self.state = 120
                    self.match(AgentSpecFullParser.LPAREN)
                    self.state = 121
                    self.match(AgentSpecFullParser.STRING)
                    self.state = 122
                    self.match(AgentSpecFullParser.RPAREN)


                pass
            elif token in [23]:
                self.enterOuterAlt(localctx, 2)
                self.state = 125
                self.actionInvoke()
                pass
            elif token in [29]:
                self.enterOuterAlt(localctx, 3)
                self.state = 126
                self.config()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ActionInvokeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def INVOKE(self):
            return self.getToken(AgentSpecFullParser.INVOKE, 0)

        def LPAREN(self):
            return self.getToken(AgentSpecFullParser.LPAREN, 0)

        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(AgentSpecFullParser.COMMA)
            else:
                return self.getToken(AgentSpecFullParser.COMMA, i)

        def LBRACE(self):
            return self.getToken(AgentSpecFullParser.LBRACE, 0)

        def kvPair(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.KvPairContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.KvPairContext,i)


        def RBRACE(self):
            return self.getToken(AgentSpecFullParser.RBRACE, 0)

        def RPAREN(self):
            return self.getToken(AgentSpecFullParser.RPAREN, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_actionInvoke

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterActionInvoke" ):
                listener.enterActionInvoke(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitActionInvoke" ):
                listener.exitActionInvoke(self)




    def actionInvoke(self):

        localctx = AgentSpecFullParser.ActionInvokeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_actionInvoke)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 129
            self.match(AgentSpecFullParser.INVOKE)
            self.state = 130
            self.match(AgentSpecFullParser.LPAREN)
            self.state = 131
            self.match(AgentSpecFullParser.IDENTIFIER)
            self.state = 132
            self.match(AgentSpecFullParser.COMMA)
            self.state = 133
            self.match(AgentSpecFullParser.LBRACE)
            self.state = 134
            self.kvPair()
            self.state = 139
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==10:
                self.state = 135
                self.match(AgentSpecFullParser.COMMA)
                self.state = 136
                self.kvPair()
                self.state = 141
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 142
            self.match(AgentSpecFullParser.RBRACE)
            self.state = 143
            self.match(AgentSpecFullParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class KvPairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(AgentSpecFullParser.STRING, 0)

        def COLON(self):
            return self.getToken(AgentSpecFullParser.COLON, 0)

        def value(self):
            return self.getTypedRuleContext(AgentSpecFullParser.ValueContext,0)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_kvPair

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterKvPair" ):
                listener.enterKvPair(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitKvPair" ):
                listener.exitKvPair(self)




    def kvPair(self):

        localctx = AgentSpecFullParser.KvPairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_kvPair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 145
            self.match(AgentSpecFullParser.STRING)
            self.state = 146
            self.match(AgentSpecFullParser.COLON)
            self.state = 147
            self.value(0)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(AgentSpecFullParser.STRING, 0)

        def number(self):
            return self.getTypedRuleContext(AgentSpecFullParser.NumberContext,0)


        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def actionInvoke(self):
            return self.getTypedRuleContext(AgentSpecFullParser.ActionInvokeContext,0)


        def value(self):
            return self.getTypedRuleContext(AgentSpecFullParser.ValueContext,0)


        def LBRACK(self):
            return self.getToken(AgentSpecFullParser.LBRACK, 0)

        def RBRACK(self):
            return self.getToken(AgentSpecFullParser.RBRACK, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_value

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterValue" ):
                listener.enterValue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitValue" ):
                listener.exitValue(self)



    def value(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = AgentSpecFullParser.ValueContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 30
        self.enterRecursionRule(localctx, 30, self.RULE_value, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 154
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [30]:
                self.state = 150
                self.match(AgentSpecFullParser.STRING)
                pass
            elif token in [31, 32]:
                self.state = 151
                self.number()
                pass
            elif token in [29]:
                self.state = 152
                self.match(AgentSpecFullParser.IDENTIFIER)
                pass
            elif token in [23]:
                self.state = 153
                self.actionInvoke()
                pass
            else:
                raise NoViableAltException(self)

            self._ctx.stop = self._input.LT(-1)
            self.state = 162
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,13,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    localctx = AgentSpecFullParser.ValueContext(self, _parentctx, _parentState)
                    self.pushNewRecursionContext(localctx, _startState, self.RULE_value)
                    self.state = 156
                    if not self.precpred(self._ctx, 2):
                        from antlr4.error.Errors import FailedPredicateException
                        raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                    self.state = 157
                    self.match(AgentSpecFullParser.LBRACK)
                    self.state = 158
                    self.match(AgentSpecFullParser.STRING)
                    self.state = 159
                    self.match(AgentSpecFullParser.RBRACK) 
                self.state = 164
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,13,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class NumberContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def INTEGER(self):
            return self.getToken(AgentSpecFullParser.INTEGER, 0)

        def FLOAT(self):
            return self.getToken(AgentSpecFullParser.FLOAT, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_number

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterNumber" ):
                listener.enterNumber(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitNumber" ):
                listener.exitNumber(self)




    def number(self):

        localctx = AgentSpecFullParser.NumberContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_number)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 165
            _la = self._input.LA(1)
            if not(_la==31 or _la==32):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ConfigContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def EQ(self):
            return self.getToken(AgentSpecFullParser.EQ, 0)

        def number(self):
            return self.getTypedRuleContext(AgentSpecFullParser.NumberContext,0)


        def namespace(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AgentSpecFullParser.NamespaceContext)
            else:
                return self.getTypedRuleContext(AgentSpecFullParser.NamespaceContext,i)


        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_config

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterConfig" ):
                listener.enterConfig(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitConfig" ):
                listener.exitConfig(self)




    def config(self):

        localctx = AgentSpecFullParser.ConfigContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_config)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 168 
            self._errHandler.sync(self)
            _alt = 1
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt == 1:
                    self.state = 167
                    self.namespace()

                else:
                    raise NoViableAltException(self)
                self.state = 170 
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,14,self._ctx)

            self.state = 172
            self.match(AgentSpecFullParser.IDENTIFIER)
            self.state = 173
            self.match(AgentSpecFullParser.EQ)
            self.state = 174
            self.number()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NamespaceContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AgentSpecFullParser.IDENTIFIER, 0)

        def COLON(self):
            return self.getToken(AgentSpecFullParser.COLON, 0)

        def getRuleIndex(self):
            return AgentSpecFullParser.RULE_namespace

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterNamespace" ):
                listener.enterNamespace(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitNamespace" ):
                listener.exitNamespace(self)




    def namespace(self):

        localctx = AgentSpecFullParser.NamespaceContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_namespace)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 176
            self.match(AgentSpecFullParser.IDENTIFIER)
            self.state = 177
            self.match(AgentSpecFullParser.COLON)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[15] = self.value_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def value_sempred(self, localctx:ValueContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 2)
         




