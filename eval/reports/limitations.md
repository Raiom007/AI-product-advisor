# Known Limitations

- Spec-based constraint checking (RAM, screen size, etc.) is currently unreliable on real McAuley data because specs_parser's regex fallback doesn't match extracted values against canonical units - this is a known limitation, not silently fixed.
