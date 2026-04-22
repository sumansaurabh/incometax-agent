"""Registers every agent tool with `tool_registry` on package import.

Importing this package has the side effect of executing each tool module, which runs the
`@tool_registry.tool(...)` decorators and populates the registry. The runner never imports
individual tool modules directly; it only reads from `tool_registry`.

When adding a new tool, create a module under this package and add it to the imports below.
"""

from itx_backend.agent.tools import document_search as _document_search  # noqa: F401
from itx_backend.agent.tools import extract_facts as _extract_facts  # noqa: F401
from itx_backend.agent.tools import kb_lookup as _kb_lookup  # noqa: F401
from itx_backend.agent.tools import portal_context as _portal_context  # noqa: F401
from itx_backend.agent.tools import tax_calc as _tax_calc  # noqa: F401

__all__: list[str] = []
