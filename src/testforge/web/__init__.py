"""Server-rendered web interface.

Depends on GenerationService directly and never re-enters the application over
HTTP: the API and this layer are siblings, not stacked.
"""
