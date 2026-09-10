/*
 * AgentSpecFull -- a permissive grammar for *reading* the AgentSpec corpus.
 * plan.md S3.1.
 *
 * The shipped grammar, src/spec_lang/AgentSpec.g4, is deliberately left
 * untouched. It rejects 21 of the 42 rules in its own repository, and that is a
 * finding worth keeping measurable (docs/baseline-audit.md, frozen at the
 * commit it was generated from). Repairing it in place would turn that finding
 * into history and would make "AgentSpec" in every later experiment mean a
 * version we had fixed.
 *
 * So this is a second grammar, used only by our compiler front end (S3.3) and
 * by `tools/audit_rules.py --grammar full`. It accepts a superset: everything
 * the shipped grammar accepts, plus every construct the corpus actually uses.
 *
 * What it adds, and which corpus file forced it:
 *
 *   //, /* *\/ comments        all three .ar files -- the shipped grammar has
 *                              no comment token at all, so `// index0` is a
 *                              lexer error on the first character
 *   True / False               toolemu.ar writes them capitalised
 *   dotted events              toolemu.ar: Gmail.SendMail
 *   alternation with |         toolemu.ar: A.B | C.D | E.F
 *   multi-word events          embodied.ar: `turn on`
 *   open predicate names       the shipped grammar hard-codes 36 names as a
 *                              lexer token, so a rule naming any other
 *                              predicate cannot parse
 *   llm_self_examine           toolemu.ar; the shipped token is
 *                              llm_self_reflect and the README uses the other
 *   enforcement arguments      toolemu.ar: user_inspection("...")
 *   & between checks           apollo/*.rule: a(1) & b(2)
 *   trigger any                ANY is declared in the shipped grammar and never
 *                              referenced by a parser rule -- a dead token
 *
 * Accepting a construct is not the same as being able to execute it. This
 * grammar exists to let the compiler *see* the whole corpus; what each rule
 * then means is S3.3's problem, and docs/coverage.md (S3.5) reports how much of
 * it survives the trip.
 */
grammar AgentSpecFull;

// ------------------------------------------------------------------ lexer

RULE: 'rule';
TRIGGER: 'trigger';
CHECK: 'check';
ENFORCE: 'enforce';
ANY: 'any';
TRUE: 'true' | 'True';
FALSE: 'false' | 'False';
END: 'end';

COLON: ':';
COMMA: ',';
LPAREN: '(';
RPAREN: ')';
LBRACE: '{';
RBRACE: '}';
DOT: '.';
LBRACK: '[';
RBRACK: ']';
AT: '@';
EQ: '=';
NOT: '!';
AND: '&';
OR: '|';

INVOKE: 'invoke_action';

// llm_self_examine is the name the README and toolemu.ar use; llm_self_reflect
// is the one the shipped grammar declares. Both are accepted here and the
// compiler normalises them (see agentguard/compile.py, S3.3).
ENFORCEMENT
    : 'user_inspection'
    | 'llm_self_reflect'
    | 'llm_self_examine'
    | 'stop'
    | 'none'
    | 'skip'
    ;

STATE_CHANGE: 'state_change';
BEFORE_ACTION: 'before_action';
AFTER_ACTION: 'after_action';
FINISH: 'finish';

// Predicate names are *not* a closed token list here. The shipped grammar bakes
// 36 of them into the lexer, which is why adding a predicate needs an ANTLR
// regeneration and why any rule naming a 37th cannot parse.
IDENTIFIER: [a-zA-Z_][a-zA-Z0-9_]*;
STRING: '"' .*? '"';
INTEGER: [0-9]+;
FLOAT: [0-9]+ '.' [0-9]* | '.' [0-9]+;

LINE_COMMENT: '//' ~[\r\n]* -> skip;
BLOCK_COMMENT: '/*' .*? '*/' -> skip;
WS: [ \t\r\n]+ -> skip;

// ----------------------------------------------------------------- parser

program: rule* EOF;

rule: ruleClause triggerClause checkClause enforceClause END;

ruleClause: RULE AT IDENTIFIER;

triggerClause: TRIGGER event;

// `A | B | C` -- any of several tools arms the rule.
event: eventTerm (OR eventTerm)*;

// `turn on` is two words; `Gmail.SendMail` is one dotted path. Both occur, and
// they mean different things, so the tree keeps them apart rather than
// concatenating -- getText() on the old grammar would have produced "turnon".
eventTerm: eventPath+;

eventPath: eventWord (DOT eventWord)*;

eventWord: IDENTIFIER | STATE_CHANGE | BEFORE_ACTION | AFTER_ACTION | FINISH | ANY;

// `&` is optional: the corpus writes both `a b` and `a & b`, and both mean AND.
checkClause: CHECK predicate (AND? predicate)*;

enforceClause: ENFORCE enforcement+;

// predicateFunc first: `v_f_disL(10)` must not be read as a bare name followed
// by a stray paren.
predicate
    : TRUE
    | FALSE
    | NOT predicate
    | predicateFunc
    | IDENTIFIER
    ;

predicateFunc: IDENTIFIER LPAREN number (COMMA number)* RPAREN;

// `user_inspection("make sure the request is reasonable")` -- an enforcement
// with a message. The shipped grammar has ENFORCEMENT as a bare token.
enforcement
    : ENFORCEMENT (LPAREN STRING RPAREN)?
    | actionInvoke
    | config
    ;

actionInvoke: INVOKE LPAREN IDENTIFIER COMMA LBRACE kvPair (COMMA kvPair)* RBRACE RPAREN;

kvPair: STRING COLON value;

value: STRING | number | IDENTIFIER | value LBRACK STRING RBRACK | actionInvoke;

number: INTEGER | FLOAT;

// apollo: `real:obstacle:Min_stop_distance = 10`
config: namespace+ IDENTIFIER EQ number;

namespace: IDENTIFIER COLON;
