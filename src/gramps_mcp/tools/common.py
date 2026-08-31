# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Helpers shared across the MCP tool modules.
"""

import logging

from ..client import GrampsAPIError

logger = logging.getLogger(__name__)


def format_error_response(error: Exception, operation: str) -> None:
    """
    Raise a GrampsAPIError so the MCP framework reports isError=true.

    Args:
        error (Exception): The exception a tool caught.
        operation (str): Human-readable name of the failed operation.

    Raises:
        GrampsAPIError: Always. Returning an "Error: ..." message instead made
            the MCP framework treat the failure as a successful response, so
            callers could not tell a real result from a failure.
    """
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    raise GrampsAPIError(error_msg)
