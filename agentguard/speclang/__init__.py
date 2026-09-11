"""A permissive parser for the AgentSpec corpus (plan.md S3.1).

The shipped grammar in `src/spec_lang/` is left untouched -- it rejects 21 of
the 42 rules in its own repository, and that is a measured finding rather than
something to quietly repair. This package holds a second grammar that accepts
everything the corpus actually uses, for the compiler front end (S3.3) and for
`tools/audit_rules.py --grammar full`.

Regenerate after editing the .g4:

    java -jar src/spec_lang/antlr-4.13.2-complete.jar -Dlanguage=Python3 \
         -o agentguard/speclang agentguard/speclang/AgentSpecFull.g4
"""
