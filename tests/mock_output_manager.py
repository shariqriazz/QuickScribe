"""
Mock output manager for testing without executing real xdotool commands.
"""

class MockOutputManager:
    """Mock output manager that tracks operations without executing them."""
    
    def __init__(self):
        self.operations = []  # Track all operations for testing
        self.typed_text = ""  # Accumulate what would be typed
        
    def backspace(self, count):
        """Mock backspace operation."""
        self.operations.append(('backspace', count))
        # Remove characters from the end
        self.typed_text = self.typed_text[:-count] if count <= len(self.typed_text) else ""
        
    def type_text(self, text):
        """Mock type text operation."""
        self.operations.append(('type', text))
        self.typed_text += text
        
    def execute_diff(self, diff_result):
        """Mock execute diff operation."""
        self.operations.append(('execute_diff', diff_result))
        if hasattr(diff_result, 'backspaces') and diff_result.backspaces > 0:
            self.backspace(diff_result.backspaces)
        if hasattr(diff_result, 'new_text') and diff_result.new_text:
            self.type_text(diff_result.new_text)
            
    def reset(self):
        """Reset mock state."""
        self.operations.clear()
        self.typed_text = ""
        
    def get_final_text(self):
        """Get the final accumulated text."""
        return self.typed_text
        
    def get_operations(self):
        """Get list of all operations performed."""
        return self.operations.copy()
    
    def clear_calls(self):
        """Clear all recorded operations (alias for reset)."""
        self.operations.clear()
        
    def get_calls(self):
        """Get operations in format expected by tests."""
        calls = []
        for op_type, data in self.operations:
            if op_type == 'backspace':
                calls.append({'operation': 'backspace', 'count': data})
            elif op_type == 'type':
                calls.append({'operation': 'type', 'text': data})
            else:
                calls.append({'operation': op_type, 'data': data})
        return calls