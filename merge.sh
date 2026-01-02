#!/bin/bash

# Name of the output file
OUTPUT_FILE="full_project_context.txt"

# Remove the output file if it already exists so we don't append to it
if [ -f "$OUTPUT_FILE" ]; then
    rm "$OUTPUT_FILE"
fi

echo "Generating $OUTPUT_FILE..."

# 1. Start looking in current directory (.)
# 2. Prune (ignore) specific directories (venv, .git, __pycache__, node_modules)
# 3. Look for files (-type f)
# 4. Exclude specific extensions (.pyc, .log, .db, .png, etc.)
# 5. Execute the formatting loop

find . \
    \( -name "venv" -o -name ".venv" -o -name "__pycache__" -o -name ".git" -o -name ".idea" -o -name ".vscode" \) -prune \
    -o -type f \
    -not -name "*.pyc" \
    -not -name "*.log" \
    -not -name "*.db" \
    -not -name "*.sqlite" \
    -not -name ".DS_Store" \
    -not -name "$OUTPUT_FILE" \
    -not -name "merge_project.sh" \
    -print0 | while IFS= read -r -d '' file; do

    # Get the absolute path for the header (as requested)
    # If 'realpath' is not installed on your system, you can use: abs_path=$(cd "$(dirname "$file")"; pwd)/$(basename "$file")
    abs_path=$(realpath "$file")

    # Append Header
    echo "----------------------------------------------------------------" >> "$OUTPUT_FILE"
    echo "----- $abs_path -----" >> "$OUTPUT_FILE"
    echo "----------------------------------------------------------------" >> "$OUTPUT_FILE"

    # Append Content
    cat "$file" >> "$OUTPUT_FILE"

    # Add a couple of newlines between files for readability
    echo -e "\n\n" >> "$OUTPUT_FILE"

done

echo "Done! Content saved to $OUTPUT_FILE"