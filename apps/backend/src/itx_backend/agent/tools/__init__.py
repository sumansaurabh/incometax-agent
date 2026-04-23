"""Registers every agent tool with `tool_registry` on package import.

Importing this package has the side effect of executing each tool module, which runs the
`@tool_registry.tool(...)` decorators and populates the registry. The runner never imports
individual tool modules directly; it only reads from `tool_registry`.

When adding a new tool, create a module under this package and add it to the imports below.
"""

from itx_backend.agent.tools import document_search as _document_search  # noqa: F401
from itx_backend.agent.tools import extract_facts as _extract_facts  # noqa: F401
from itx_backend.agent.tools import get_form_schema as _get_form_schema  # noqa: F401
from itx_backend.agent.tools import get_validation_errors as _get_validation_errors  # noqa: F401
from itx_backend.agent.tools import how_to as _how_to  # noqa: F401
from itx_backend.agent.tools import kb_lookup as _kb_lookup  # noqa: F401
from itx_backend.agent.tools import portal_context as _portal_context  # noqa: F401
from itx_backend.agent.tools import portal_nav as _portal_nav  # noqa: F401
from itx_backend.agent.tools import propose_fill as _propose_fill  # noqa: F401
from itx_backend.agent.tools import read_portal_field as _read_portal_field  # noqa: F401
from itx_backend.agent.tools import resolve_document_password as _resolve_document_password  # noqa: F401
from itx_backend.agent.tools import tax_calc as _tax_calc  # noqa: F401
from itx_backend.agent.tools import web_search as _web_search  # noqa: F401

__all__: list[str] = []
