import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import argparse
import sys
import os
from datetime import datetime
import itertools
import re

# Try to import required libraries
try:
    import zxcvbn
    ZXCVBN_AVAILABLE = True
except ImportError:
    ZXCVBN_AVAILABLE = False
    print("Warning: zxcvbn not available. Install with: pip install zxcvbn")

try:
    import nltk
    NLTK_AVAILABLE = True
    # Download required NLTK data
    try:
        nltk.data.find('corpora/words')
    except LookupError:
        nltk.download('words', quiet=True)
except ImportError:
    NLTK_AVAILABLE = False
    print("Warning: nltk not available. Install with: pip install nltk")

class PasswordAnalyzer:
    def __init__(self):
        self.leet_speak_map = {
            'a': ['@', '4'],
            'e': ['3'],
            'i': ['1', '!'],
            'o': ['0'],
            's': ['5', '$'],
            't': ['7'],
            'b': ['8'],
            'g': ['9'],
            'l': ['1']
        }
        
        self.common_suffixes = ['!', '@', '#', '$', '%', '&', '*', '123', '1234']
        
    def analyze_password(self, password):
        """Analyze password strength using zxcvbn or custom calculations"""
        if ZXCVBN_AVAILABLE:
            return self._analyze_with_zxcvbn(password)
        else:
            return self._analyze_custom(password)
    
    def _analyze_with_zxcvbn(self, password):
        """Analyze password using zxcvbn library"""
        result = zxcvbn.zxcvbn(password)
        
        analysis = {
            'password': password,
            'score': result['score'],
            'feedback': result['feedback'],
            'crack_time': result['crack_times_display']['offline_fast_hashing_1e10_per_second'],
            'guesses': result['guesses'],
            'patterns': [match['pattern'] for match in result['sequence']]
        }
        
        return analysis
    
    def _analyze_custom(self, password):
        """Custom password analysis when zxcvbn is not available"""
        score = 0
        feedback = []
        
        # Length check
        if len(password) >= 12:
            score += 2
        elif len(password) >= 8:
            score += 1
        else:
            feedback.append("Password should be at least 8 characters long")
        
        # Character variety checks
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        variety_count = sum([has_upper, has_lower, has_digit, has_special])
        
        if variety_count >= 3:
            score += 1
        else:
            feedback.append("Use a mix of uppercase, lowercase, numbers, and special characters")
        
        # Common pattern checks
        common_patterns = ['123', 'abc', 'qwerty', 'password', 'admin']
        if any(pattern in password.lower() for pattern in common_patterns):
            score = max(0, score - 1)
            feedback.append("Avoid common patterns and words")
        
        # Entropy calculation (simplified)
        char_set_size = 0
        if has_upper: char_set_size += 26
        if has_lower: char_set_size += 26
        if has_digit: char_set_size += 10
        if has_special: char_set_size += 32
        
        if char_set_size > 0:
            entropy = len(password) * (char_set_size.bit_length())
        else:
            entropy = 0
            
        # Convert entropy to crack time estimation
        if entropy > 100:
            crack_time = "centuries"
        elif entropy > 80:
            crack_time = "years"
        elif entropy > 60:
            crack_time = "months"
        elif entropy > 40:
            crack_time = "days"
        elif entropy > 20:
            crack_time = "hours"
        else:
            crack_time = "minutes"
        
        return {
            'password': password,
            'score': min(4, score),
            'feedback': feedback if feedback else ["Good password practices"],
            'crack_time': crack_time,
            'guesses': 10 ** (entropy / 10) if entropy > 0 else 1000,
            'patterns': ['custom_analysis']
        }

class WordlistGenerator:
    def __init__(self):
        self.leet_map = {
            'a': ['@', '4'],
            'e': ['3'],
            'i': ['1', '!'],
            'o': ['0'],
            's': ['5', '$'],
            't': ['7'],
            'l': ['1'],
            'b': ['8']
        }
        
    def generate_wordlist(self, personal_info, options):
        """Generate custom wordlist based on personal information"""
        words = set()
        
        # Base words from personal info
        base_words = self._get_base_words(personal_info)
        
        # Apply transformations
        for word in base_words:
            words.add(word)
            words.add(word.lower())
            words.add(word.upper())
            words.add(word.capitalize())
            
            # Leetspeak variations
            if options.get('leet_speak', True):
                leet_variations = self._generate_leet_variations(word)
                words.update(leet_variations)
            
            # Add common suffixes
            if options.get('common_suffixes', True):
                for suffix in ['!', '@', '#', '$', '%', '^', '&', '*', '123', '1234', '!123']:
                    words.add(word + suffix)
                    words.add(word.lower() + suffix)
        
        # Add year combinations
        if options.get('append_years', True):
            year_words = self._append_years(list(words), 
                                          options.get('start_year', 1970), 
                                          options.get('end_year', 2024))
            words.update(year_words)
        
        # Add common patterns
        if options.get('common_patterns', True):
            pattern_words = self._generate_common_patterns(personal_info)
            words.update(pattern_words)
        
        return sorted(list(words), key=len, reverse=True)
    
    def _get_base_words(self, personal_info):
        """Extract base words from personal information"""
        words = set()
        
        # Add names
        if personal_info.get('first_name'):
            words.add(personal_info['first_name'])
        if personal_info.get('last_name'):
            words.add(personal_info['last_name'])
        if personal_info.get('nickname'):
            words.add(personal_info['nickname'])
        
        # Add pet names
        if personal_info.get('pet_name'):
            words.add(personal_info['pet_name'])
        
        # Add important dates (extract year, month, day)
        if personal_info.get('birthdate'):
            bd = personal_info['birthdate']
            # Try to parse various date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d']:
                try:
                    date_obj = datetime.strptime(bd, fmt)
                    words.add(date_obj.strftime('%Y'))  # Year
                    words.add(date_obj.strftime('%y'))  # Short year
                    words.add(date_obj.strftime('%m'))  # Month
                    words.add(date_obj.strftime('%d'))  # Day
                    words.add(date_obj.strftime('%m%d'))  # MonthDay
                    words.add(date_obj.strftime('%d%m'))  # DayMonth
                    break
                except ValueError:
                    continue
        
        # Add other personal info
        if personal_info.get('city'):
            words.add(personal_info['city'])
        if personal_info.get('company'):
            words.add(personal_info['company'])
        
        return list(words)
    
    def _generate_leet_variations(self, word):
        """Generate leetspeak variations of a word"""
        variations = set()
        word_lower = word.lower()
        
        # Simple leet substitutions
        for char, replacements in self.leet_map.items():
            if char in word_lower:
                for replacement in replacements:
                    new_word = word_lower.replace(char, replacement)
                    variations.add(new_word)
                    variations.add(new_word.capitalize())
        
        return list(variations)
    
    def _append_years(self, words, start_year, end_year):
        """Append years to words"""
        new_words = set()
        
        for word in words:
            for year in range(start_year, end_year + 1):
                new_words.add(word + str(year))
                new_words.add(word + str(year)[2:])  # Short year
                
                # Also add with common separators
                for sep in ['', '-', '_', '.']:
                    new_words.add(word + sep + str(year))
                    new_words.add(word + sep + str(year)[2:])
        
        return new_words
    
    def _generate_common_patterns(self, personal_info):
        """Generate common password patterns"""
        patterns = set()
        
        first_name = personal_info.get('first_name', '')
        last_name = personal_info.get('last_name', '')
        nickname = personal_info.get('nickname', '')
        
        # Name combinations
        if first_name and last_name:
            patterns.add(first_name + last_name)
            patterns.add(first_name + '.' + last_name)
            patterns.add(first_name + '_' + last_name)
            patterns.add(first_name[0] + last_name)
            patterns.add(first_name + last_name[0])
            patterns.add(last_name + first_name)
        
        # Common base patterns
        common_bases = ['admin', 'password', 'welcome', 'login', 'user', 'pass']
        for base in common_bases:
            patterns.add(base)
            patterns.add(base + '123')
            patterns.add(base + '!')
            patterns.add(base.capitalize() + '123')
        
        return patterns

class PasswordAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Password Strength Analyzer & Wordlist Generator")
        self.root.geometry("800x700")
        
        # Initialize components
        self.analyzer = PasswordAnalyzer()
        self.generator = WordlistGenerator()
        
        self.wordlist = []
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.analysis_frame = ttk.Frame(self.notebook)
        self.wordlist_frame = ttk.Frame(self.notebook)
        self.export_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.analysis_frame, text="Password Analysis")
        self.notebook.add(self.wordlist_frame, text="Wordlist Generator")
        self.notebook.add(self.export_frame, text="Export Wordlist")
        
        self.setup_analysis_tab()
        self.setup_wordlist_tab()
        self.setup_export_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='bottom', fill='x')
        self.status_var.set("Ready")
    
    def setup_analysis_tab(self):
        """Setup password analysis tab"""
        # Password input
        ttk.Label(self.analysis_frame, text="Enter Password to Analyze:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky='w', pady=(10,5), padx=10)
        
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(self.analysis_frame, textvariable=self.password_var, show="•", width=50, font=('Arial', 10))
        self.password_entry.grid(row=1, column=0, padx=10, pady=5, sticky='ew')
        self.password_entry.bind('<KeyRelease>', self.real_time_analysis)
        
        # Show password checkbox
        self.show_password_var = tk.BooleanVar()
        ttk.Checkbutton(self.analysis_frame, text="Show Password", 
                       variable=self.show_password_var,
                       command=self.toggle_password_visibility).grid(row=1, column=1, padx=10, pady=5)
        
        # Analyze button
        ttk.Button(self.analysis_frame, text="Analyze Password", 
                  command=self.analyze_password).grid(row=2, column=0, padx=10, pady=10, sticky='w')
        
        # Results frame
        results_frame = ttk.LabelFrame(self.analysis_frame, text="Analysis Results", padding=10)
        results_frame.grid(row=3, column=0, columnspan=2, sticky='nsew', padx=10, pady=10)
        
        # Strength meter
        ttk.Label(results_frame, text="Strength Score:").grid(row=0, column=0, sticky='w')
        self.strength_var = tk.StringVar(value="0/4")
        self.strength_label = ttk.Label(results_frame, textvariable=self.strength_var, font=('Arial', 12, 'bold'))
        self.strength_label.grid(row=0, column=1, sticky='w', padx=5)
        
        # Crack time
        ttk.Label(results_frame, text="Estimated Crack Time:").grid(row=1, column=0, sticky='w', pady=5)
        self.crack_time_var = tk.StringVar()
        ttk.Label(results_frame, textvariable=self.crack_time_var).grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        # Feedback
        ttk.Label(results_frame, text="Feedback:").grid(row=2, column=0, sticky='nw', pady=5)
        self.feedback_text = scrolledtext.ScrolledText(results_frame, width=60, height=8, font=('Arial', 9))
        self.feedback_text.grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Configure grid weights
        self.analysis_frame.columnconfigure(0, weight=1)
        results_frame.columnconfigure(1, weight=1)
    
    def setup_wordlist_tab(self):
        """Setup wordlist generator tab"""
        # Personal information frame
        personal_frame = ttk.LabelFrame(self.wordlist_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill='x', padx=10, pady=5)
        
        # Row 0
        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky='w', pady=2)
        self.first_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=20).grid(row=0, column=1, sticky='w', pady=2, padx=5)
        
        ttk.Label(personal_frame, text="Last Name:").grid(row=0, column=2, sticky='w', pady=2, padx=(20,0))
        self.last_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=20).grid(row=0, column=3, sticky='w', pady=2, padx=5)
        
        # Row 1
        ttk.Label(personal_frame, text="Nickname:").grid(row=1, column=0, sticky='w', pady=2)
        self.nickname_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.nickname_var, width=20).grid(row=1, column=1, sticky='w', pady=2, padx=5)
        
        ttk.Label(personal_frame, text="Pet Name:").grid(row=1, column=2, sticky='w', pady=2, padx=(20,0))
        self.pet_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.pet_name_var, width=20).grid(row=1, column=3, sticky='w', pady=2, padx=5)
        
        # Row 2
        ttk.Label(personal_frame, text="Birthdate (YYYY-MM-DD):").grid(row=2, column=0, sticky='w', pady=2)
        self.birthdate_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.birthdate_var, width=20).grid(row=2, column=1, sticky='w', pady=2, padx=5)
        
        ttk.Label(personal_frame, text="City:").grid(row=2, column=2, sticky='w', pady=2, padx=(20,0))
        self.city_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.city_var, width=20).grid(row=2, column=3, sticky='w', pady=2, padx=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(self.wordlist_frame, text="Generation Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=5)
        
        self.leet_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Leetspeak substitutions", variable=self.leet_var).grid(row=0, column=0, sticky='w')
        
        self.suffixes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Common suffixes", variable=self.suffixes_var).grid(row=0, column=1, sticky='w')
        
        self.years_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Append years", variable=self.years_var).grid(row=1, column=0, sticky='w')
        
        self.patterns_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Common patterns", variable=self.patterns_var).grid(row=1, column=1, sticky='w')
        
        # Year range
        ttk.Label(options_frame, text="Year Range:").grid(row=2, column=0, sticky='w', pady=(10,2))
        year_frame = ttk.Frame(options_frame)
        year_frame.grid(row=2, column=1, sticky='w', pady=(10,2))
        
        self.start_year_var = tk.StringVar(value="1970")
        ttk.Entry(year_frame, textvariable=self.start_year_var, width=6).pack(side='left')
        ttk.Label(year_frame, text="to").pack(side='left', padx=5)
        self.end_year_var = tk.StringVar(value="2024")
        ttk.Entry(year_frame, textvariable=self.end_year_var, width=6).pack(side='left')
        
        # Generate button
        ttk.Button(self.wordlist_frame, text="Generate Wordlist", 
                  command=self.generate_wordlist).pack(pady=10)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(self.wordlist_frame, text="Wordlist Preview (First 50 items)", padding=10)
        preview_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=15, font=('Arial', 9))
        self.preview_text.pack(fill='both', expand=True)
        
        # Wordlist info
        info_frame = ttk.Frame(self.wordlist_frame)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(info_frame, text="Total words:").pack(side='left')
        self.wordcount_var = tk.StringVar(value="0")
        ttk.Label(info_frame, textvariable=self.wordcount_var, font=('Arial', 10, 'bold')).pack(side='left', padx=5)
    
    def setup_export_tab(self):
        """Setup export tab"""
        # Export options
        options_frame = ttk.LabelFrame(self.export_frame, text="Export Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(options_frame, text="Filename:").grid(row=0, column=0, sticky='w')
        self.filename_var = tk.StringVar(value="custom_wordlist.txt")
        ttk.Entry(options_frame, textvariable=self.filename_var, width=30).grid(row=0, column=1, sticky='w', padx=5)
        
        ttk.Button(options_frame, text="Browse", command=self.browse_file).grid(row=0, column=2, padx=5)
        
        # Export button
        ttk.Button(self.export_frame, text="Export Wordlist", 
                  command=self.export_wordlist).pack(pady=10)
        
        # Export info
        info_frame = ttk.LabelFrame(self.export_frame, text="Export Information", padding=10)
        info_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.export_info_text = scrolledtext.ScrolledText(info_frame, height=10, font=('Arial', 9))
        self.export_info_text.pack(fill='both', expand=True)
        
        # Update export info
        self.update_export_info()
    
    def real_time_analysis(self, event=None):
        """Perform real-time password analysis"""
        password = self.password_var.get()
        if len(password) > 0:
            self.analyze_password()
    
    def toggle_password_visibility(self):
        """Toggle password visibility"""
        if self.show_password_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="•")
    
    def analyze_password(self):
        """Analyze the entered password"""
        password = self.password_var.get()
        
        if not password:
            messagebox.showwarning("Input Error", "Please enter a password to analyze")
            return
        
        try:
            analysis = self.analyzer.analyze_password(password)
            
            # Update strength score with color
            score = analysis['score']
            self.strength_var.set(f"{score}/4")
            
            # Set color based on score
            colors = ['#ff4444', '#ff8800', '#ffcc00', '#aacc00', '#00aa00']
            self.strength_label.config(foreground=colors[score] if score < len(colors) else colors[-1])
            
            # Update crack time
            self.crack_time_var.set(analysis['crack_time'])
            
            # Update feedback
            self.feedback_text.delete(1.0, tk.END)
            
            feedback_text = "Strengths:\n"
            if score >= 3:
                feedback_text += "• Good password length and complexity\n"
            if score >= 4:
                feedback_text += "• Excellent password security\n"
            
            feedback_text += "\nAreas for improvement:\n"
            for suggestion in analysis['feedback']:
                feedback_text += f"• {suggestion}\n"
            
            feedback_text += f"\nPatterns detected: {', '.join(analysis['patterns'])}"
            feedback_text += f"\n\nEstimated guesses needed: {analysis['guesses']:,.0f}"
            
            self.feedback_text.insert(1.0, feedback_text)
            
            self.status_var.set("Password analysis completed")
            
        except Exception as e:
            messagebox.showerror("Analysis Error", f"Error analyzing password: {str(e)}")
    
    def generate_wordlist(self):
        """Generate custom wordlist"""
        # Collect personal information
        personal_info = {
            'first_name': self.first_name_var.get(),
            'last_name': self.last_name_var.get(),
            'nickname': self.nickname_var.get(),
            'pet_name': self.pet_name_var.get(),
            'birthdate': self.birthdate_var.get(),
            'city': self.city_var.get(),
            'company': ''  # Could add this field
        }
        
        # Check if we have at least some information
        if not any(personal_info.values()):
            messagebox.showwarning("Input Error", "Please enter at least one piece of personal information")
            return
        
        # Collect options
        options = {
            'leet_speak': self.leet_var.get(),
            'common_suffixes': self.suffixes_var.get(),
            'append_years': self.years_var.get(),
            'common_patterns': self.patterns_var.get(),
            'start_year': int(self.start_year_var.get()),
            'end_year': int(self.end_year_var.get())
        }
        
        try:
            self.status_var.set("Generating wordlist...")
            self.root.update()
            
            # Generate wordlist
            self.wordlist = self.generator.generate_wordlist(personal_info, options)
            
            # Update preview
            self.preview_text.delete(1.0, tk.END)
            preview_words = self.wordlist[:50]  # Show first 50 words
            for word in preview_words:
                self.preview_text.insert(tk.END, word + '\n')
            
            # Update word count
            self.wordcount_var.set(str(len(self.wordlist)))
            
            # Update export info
            self.update_export_info()
            
            self.status_var.set(f"Wordlist generated with {len(self.wordlist)} words")
            
            # Switch to export tab
            self.notebook.select(2)
            
        except Exception as e:
            messagebox.showerror("Generation Error", f"Error generating wordlist: {str(e)}")
            self.status_var.set("Error generating wordlist")
    
    def browse_file(self):
        """Browse for save file location"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=self.filename_var.get()
        )
        if filename:
            self.filename_var.set(filename)
    
    def export_wordlist(self):
        """Export wordlist to file"""
        if not self.wordlist:
            messagebox.showwarning("Export Error", "No wordlist to export. Please generate a wordlist first.")
            return
        
        filename = self.filename_var.get()
        
        if not filename:
            messagebox.showwarning("Export Error", "Please specify a filename.")
            return
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for word in self.wordlist:
                    f.write(word + '\n')
            
            # Update export info
            self.update_export_info()
            
            messagebox.showinfo("Export Successful", 
                              f"Wordlist exported successfully!\n"
                              f"Location: {filename}\n"
                              f"Total words: {len(self.wordlist):,}")
            
            self.status_var.set(f"Wordlist exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting wordlist: {str(e)}")
    
    def update_export_info(self):
        """Update export information display"""
        self.export_info_text.delete(1.0, tk.END)
        
        if self.wordlist:
            info_text = f"Wordlist Information:\n"
            info_text += f"• Total words: {len(self.wordlist):,}\n"
            info_text += f"• File size: {len(self.wordlist) * 8:,} bytes (estimated)\n"
            info_text += f"• Export format: Plain text (.txt)\n"
            info_text += f"• Compatible with: Hashcat, John the Ripper, etc.\n\n"
            
            info_text += "Export Location:\n"
            info_text += f"{self.filename_var.get()}\n\n"
            
            info_text += "Usage with cracking tools:\n"
            info_text += "• Hashcat: hashcat -a 0 -m <hash_type> <hash_file> wordlist.txt\n"
            info_text += "• John: john --wordlist=wordlist.txt <hash_file>\n"
            
            self.export_info_text.insert(1.0, info_text)
        else:
            self.export_info_text.insert(1.0, "No wordlist generated yet. Generate a wordlist in the previous tab.")

def main():
    """Main function"""
    # Check if running in CLI mode
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()

def run_gui():
    """Run the GUI application"""
    root = tk.Tk()
    app = PasswordAnalyzerGUI(root)
    root.mainloop()

def run_cli():
    """Run in command line interface mode"""
    parser = argparse.ArgumentParser(description='Password Strength Analyzer & Wordlist Generator')
    
    # Analysis mode
    parser.add_argument('--analyze', '-a', metavar='PASSWORD', help='Analyze password strength')
    
    # Wordlist generation mode
    parser.add_argument('--generate', '-g', action='store_true', help='Generate wordlist')
    parser.add_argument('--first-name', help='First name for wordlist')
    parser.add_argument('--last-name', help='Last name for wordlist')
    parser.add_argument('--nickname', help='Nickname for wordlist')
    parser.add_argument('--pet-name', help='Pet name for wordlist')
    parser.add_argument('--birthdate', help='Birthdate (YYYY-MM-DD) for wordlist')
    parser.add_argument('--output', '-o', default='wordlist.txt', help='Output filename')
    
    args = parser.parse_args()
    
    if args.analyze:
        # Analyze password
        analyzer = PasswordAnalyzer()
        result = analyzer.analyze_password(args.analyze)
        
        print(f"Password Analysis Results:")
        print(f"Strength Score: {result['score']}/4")
        print(f"Estimated Crack Time: {result['crack_time']}")
        print(f"Guesses Required: {result['guesses']:,.0f}")
        print(f"Patterns Detected: {', '.join(result['patterns'])}")
        print("\nFeedback:")
        for feedback in result['feedback']:
            print(f"- {feedback}")
    
    elif args.generate:
        # Generate wordlist
        personal_info = {
            'first_name': args.first_name or '',
            'last_name': args.last_name or '',
            'nickname': args.nickname or '',
            'pet_name': args.pet_name or '',
            'birthdate': args.birthdate or ''
        }
        
        if not any(personal_info.values()):
            print("Error: Please provide at least one piece of personal information")
            return
        
        generator = WordlistGenerator()
        wordlist = generator.generate_wordlist(personal_info, {
            'leet_speak': True,
            'common_suffixes': True,
            'append_years': True,
            'common_patterns': True,
            'start_year': 1970,
            'end_year': 2024
        })
        
        with open(args.output, 'w') as f:
            for word in wordlist:
                f.write(word + '\n')
        
        print(f"Wordlist generated with {len(wordlist)} words")
        print(f"Saved to: {args.output}")
    
    else:
        print("Please specify either --analyze or --generate option")
        print("Use --help for more information")

if __name__ == "__main__":
    main()