#!/usr/bin/env python3

import os, json

print(json.dumps(dict(os.environ), indent=2))
