"""Strata trace-capture harness (Phase 4: CLI + offline replay).

Submodules:
  replay — offline replay of a captured MCP session against current code,
            producing a hash-diff regression report.  CI-usable: exits non-zero
            on any divergence so a silent regression breaks the build.
"""
