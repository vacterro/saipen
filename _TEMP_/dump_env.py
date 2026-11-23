import os, json
json.dump(dict(sorted(os.environ.items())), open("_TEMP_/dump_out.json", "w"))
