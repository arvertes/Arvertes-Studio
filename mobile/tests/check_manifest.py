"""Strict manifest policy for this diagnostic-only Android client."""
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"

def check(path):
    root = ET.parse(path).getroot()
    if any(node.tag.startswith("uses-permission") for node in root):
        raise ValueError("Diagnostic must not request permissions.")
    application = root.find("application")
    if application is None:
        raise ValueError("Missing application.")
    for field in ("allowBackup", "usesCleartextTraffic"):
        if application.get(ANDROID + field) != "false":
            raise ValueError(field + " must be false.")
    components = [node for node in application if node.tag in
                  {"activity", "activity-alias", "provider", "service", "receiver"}]
    if len(components) != 1 or components[0].tag != "activity" or components[0].get(ANDROID + "name") != ".MainActivity":
        raise ValueError("Unexpected app component.")
    print("Manifest diagnostic policy passed.")

if __name__ == "__main__":
    check(Path(sys.argv[1]))
