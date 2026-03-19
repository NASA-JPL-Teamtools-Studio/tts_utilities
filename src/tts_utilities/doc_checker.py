import ast, os, sys, json, argparse, traceback

class DocChecker(ast.NodeVisitor):
    """An AST visitor that checks for missing docstrings in Python source files.
    
    This class traverses the Abstract Syntax Tree (AST) of a Python file to 
    identify classes, functions, and properties that lack documentation, as well 
    as ensuring function arguments are mentioned in the available docstrings.
    
    Attributes:
        stats (dict): A dictionary containing collected metrics and a list of issues.
        current_file (str): The path of the file currently being processed.
        class_doc_stack (list): A stack used to keep track of class-level docstrings 
            to support __init__ documentation fallback.
    """

    def __init__(self):
        """Initializes the DocChecker with empty statistics and stacks."""
        self.stats = {
            "issues": [],
            "total_items": 0,
            "documented_items": 0
        }
        self.current_file = ""
        self.class_doc_stack = []

    def visit_ClassDef(self, node):
        """Processes a class definition node.
        
        Checks if the class has a docstring and pushes it to the stack for child 
        nodes (like __init__) to reference if needed.

        Args:
            node (ast.ClassDef): The AST node representing the class definition.
        """
        doc = ast.get_docstring(node)
        self.class_doc_stack.append(doc)
        self.stats["total_items"] += 1
        if doc:
            self.stats["documented_items"] += 1
        else:
            self.stats["issues"].append({
                "file": self.current_file,
                "line": node.lineno,
                "type": "Missing Class Doc",
                "name": node.name,
                "context": "Class Definition"
            })
        self.generic_visit(node)
        self.class_doc_stack.pop()

    def visit_FunctionDef(self, node):
        """Processes a standard function or method definition node.

        Args:
            node (ast.FunctionDef): The AST node representing the function.
        """
        self._check_func(node)

    def visit_AsyncFunctionDef(self, node):
        """Processes an asynchronous function or method definition node.

        Args:
            node (ast.AsyncFunctionDef): The AST node representing the async function.
        """
        self._check_func(node)

    def _check_func(self, node):
        """Internal logic to analyze documentation for functions and properties.
        
        Checks for the existence of function docstrings, differentiates between 
        standard functions and properties, and validates that all arguments are 
        explicitly mentioned within the docstring text.

        Args:
            node (ast.FunctionDef | ast.AsyncFunctionDef): The node to analyze.
        """
        name = node.name
        doc = ast.get_docstring(node)
        is_property = False
        is_setter = False
        
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == 'property':
                is_property = True
            elif isinstance(dec, ast.Attribute) and dec.attr == 'setter':
                is_setter = True
        
        # Documentation usually belongs on the getter, so skip setters.
        if is_setter: 
            return

        target_doc = doc
        is_init = (name == "__init__")
        
        # Fallback: if __init__ is undocumented, check the parent class docstring.
        if is_init and not target_doc and self.class_doc_stack:
            target_doc = self.class_doc_stack[-1]

        if not is_init: 
            self.stats["total_items"] += 1
            if doc:
                self.stats["documented_items"] += 1
            else:
                issue_type = "Missing Prop Doc" if is_property else "Missing Func Doc"
                context = "Property Definition" if is_property else "Function Definition"
                self.stats["issues"].append({
                    "file": self.current_file,
                    "line": node.lineno,
                    "type": issue_type,
                    "name": name,
                    "context": context
                })

        # Collate all arguments, excluding 'self' and 'cls'.
        args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
        if node.args.vararg: args.append(node.args.vararg.arg)
        if node.args.kwarg: args.append(node.args.kwarg.arg)
        args = [a for a in args if a not in ['self', 'cls']]
        
        for arg in args:
            self.stats["total_items"] += 1
            if target_doc:
                if arg in target_doc:
                    self.stats["documented_items"] += 1
                else:
                    self.stats["issues"].append({
                        "file": self.current_file, 
                        "line": node.lineno, 
                        "type": "Missing Arg Doc",
                        "name": arg, 
                        "context": f"in {name}(...)"
                    })
            else:
                self.stats["issues"].append({
                    "file": self.current_file, 
                    "line": node.lineno, 
                    "type": "Missing Arg Doc",
                    "name": arg, 
                    "context": f"in {name}(...) (No docstring found)"
                })

def run_check(target_dir):
    """Walks through a directory and runs the DocChecker on all Python files.
    
    Finds every .py file (excluding test files), parses them into ASTs, and 
    invokes the checker. Results are printed as a JSON string to stdout.

    Args:
        target_dir (str): The root directory path to scan for Python files.
    """
    try:
        if not os.path.exists(target_dir):
            print(json.dumps({"score": 0, "issues": []}))
            return
            
        checker = DocChecker()
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".py") and "test" not in file:
                    full_path = os.path.join(root, file)
                    checker.current_file = os.path.relpath(full_path, target_dir)
                    with open(full_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                        checker.visit(tree)

        score = (checker.stats["documented_items"] / checker.stats["total_items"] * 100) if checker.stats["total_items"] > 0 else 0
        print(json.dumps({"score": round(score, 1), "issues": checker.stats["issues"]}))
    except Exception:
        print(json.dumps({"score": 0, "issues": []}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan a directory for missing Python docstrings.")
    parser.add_argument("--target", required=True, help="The directory to scan.")
    args = parser.parse_args()
    run_check(args.target)