# PyASM - An Assembly-like Programming Language
An assembly-like programming language built entirely with Python
You can also download the `.exe` file if you dont want any assets.

# File Structure (for the `.py` file) 
`
PyASM-IDE/
   PyASM_IDE.py
   ico/
      pyasmide.py
   fonts/
      DOSfont.ttf
      CascadiaMono.ttf
`
You can edit these files except the `.py` file to customize
your IDE.

# PyASM IDE — User Guide
---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Running the IDE](#running-the-ide)
4. [IDE Layout](#ide-layout)
5. [Language Reference](#language-reference)
   - [Comments](#comments)
   - [Variables](#variables)
   - [Registers](#registers)
   - [Register Operations](#register-operations)
   - [Arithmetic](#arithmetic)
   - [Comparison](#comparison)
   - [Input and Output](#input-and-output)
   - [Functions](#functions)
   - [Loops](#loops)
   - [Control Flow](#control-flow)
6. [Error Types](#error-types)
7. [Saving and Loading Files](#saving-and-loading-files)
8. [Custom Fonts](#custom-fonts)
9. [Running Without Kivy](#running-without-kivy)
10. [Example Program](#example-program)

---

## Requirements

- Python 3.8 or newer
- Kivy 2.0 or newer

---

## Installation

Install Kivy using pip:

```bash
pip install kivy
```

Download here: https://www.python.org/downloads/
No other dependencies are required. The virtual machine itself is
pure Python.

---

## Running the IDE

```bash
python pyasm_ide.py
```

If Kivy is not installed the script falls back to a headless mode that
runs the built-in demo program and prints results to the terminal.

---

## IDE Layout

The window is divided into three sections.

**Toolbar** runs across the top and contains
these buttons:

New File - Clears the editor and resets the VM
Save File - Saves the current code to a `.pyasm` file
Load File - Opens a file browser to load a `.pyasm` file
Step - Loads the program (first press) then executes one instruction at a time
Run - Loads and runs the entire program in one go
Reset Registers - Resets the VM state without clearing the editor
Help - Opens a quick-reference popup

**Editor and Console** sit side by side below the toolbar. Write your PyASM
code on the left. Output from `out` instructions and any error messages appear
on the right. The status bar at the bottom of the console shows the current
program counter, execution status, variable count, and function count.

**Register Panel** sits at the bottom of the window and shows all 16 registers.
Each box displays the register name and its current list of values. The panel
scrolls horizontally so all 16 registers are always accessible. Register values
update automatically after every instruction.

---

## Language Reference

### Comments

Anything after `//` on a line is ignored.

```
append reg1 10   // this is a comment
// this whole line is a comment
```

---

### Variables

Variables store a single integer or string value. They are declared
with `var` and can be read by most instructions.

```
var x = 10
var message = 'hello world'
var copy = x
```

The right-hand side can be a literal integer, a hex literal, a string in
single or double quotes, or the name of an existing variable or register
(which reads the last value of that register).

---

### Registers

There are 16 registers named `reg1` through `reg16`. Each register is 
a **list of integers**. Most operations read from and write to the
**last element** of the list (like a stack top). A register starts
empty and grows as values are appended to it.

---

### Register Operations

**append** — push a value onto a register

```
append reg1 42
append reg2 reg1    // pushes the last value of reg1 onto reg2
append reg3 x       // pushes the value of variable x
```

**mov** — move all values from one register to another. The source
register is cleared.

```
mov reg2 reg1       // reg2 gets all of reg1's values; reg1 becomes empty
```

**xchg** — swap the entire contents of two registers

```
xchg reg1 reg2
```

**Increment and decrement** — modify the last element of a register in place

```
reg1+5              // adds 5 to reg1's last element
reg1-3              // subtracts 3 from reg1's last element
```

---

### Arithmetic

All arithmetic instructions append their result to the destination register.
They read the last element of each source register (or resolve the token as
a variable or literal).

```
add reg3 reg1 reg2   // reg3 gets reg1[-1] + reg2[-1]
sub reg3 reg1 reg2   // reg3 gets reg1[-1] - reg2[-1]
mul reg3 reg1 reg2   // reg3 gets reg1[-1] * reg2[-1]
div reg3 reg1 reg2   // reg3 gets reg1[-1] // reg2[-1]  (integer division)
```

You can also use variable names or literals as the source operands:

```
var a = 10
append reg1 3
add reg2 a reg1      // 10 + 3 = 13, appended to reg2
```

Division by zero raises an `Undefined Value Error`.

---

### Comparison

`cmp` compares two values and appends `1` or `0` to the destination register.

```
cmp reg4 reg1 reg2   // appends 1 if reg1[-1] >= reg2[-1], else 0
```

---

### Input and Output

**out** — print a value to the console

```
out reg1             // prints the full list stored in reg1
out x                // prints the value of variable x
out 'hello'          // prints the string literally
out "world"          // double quotes work too
```

**input** — prompt the user for a value and store it in a register. The
value is interpreted as a hexadecimal integer first, then as a decimal
integer if that fails.

```
input "Enter a value" reg1
input 'Enter hex'     reg2
```

A popup dialog appears in the IDE when `input` is reached during execution.

---

### Functions

A function is a named block of instructions. It is defined once and can be
called any number of times. Functions are **not executed at definition time**.

```
define greet
  out 'Hello!'
  append reg1 1
end

call greet
call greet     // can be called multiple times
```

Functions can call other functions. Recursive calls are supported but there
is no call-depth limit enforced by the VM, so infinite recursion will crash Python.

---

### Loops

A loop repeats a block of instructions a fixed number of times. Instructions
inside the loop are separated by semicolons. If the repeat count is omitted 
it defaults to 1.

```
[ reg1+1 ]5                 // increment reg1's top value 5 times

[ append reg2 0; reg1+1 ]3  // two instructions, repeated 3 times
```

The loop syntax is a single line. For more complex repeated logic, put the
body in a function and call it inside the loop:

```
define body
  reg1+1
  out reg1
end

[ call body ]10
```

----

### Control Flow

**exit** — immediately halts execution

```
exit
```

**skip** — a no-op, does nothing

```
skip
```

---

## Error Types


`Syntax Error` - An unrecognised instruction or malformed statement
`Register Name Error` - A register name that is not `reg1`–`reg16'
`Undefined Value Error` - An empty register read, an unknown variable,
an invalid input value, or division by zero

Errors are printed to the console panel and execution stops. The program
counter and register state at the point of failure are preserved so you
can inspect them.

---

## Saving and Loading Files

Files are saved with the `.pyasm` extension to the following folder:

```
~/Python Assembly Files/
```

The folder is created automatically if it does not exist. Click **Save File**, type
a filename without extension, and press Enter or click Save. Click **Load File** to
browse and open any `.pyasm` file from that folder.

---

## Custom Fonts

The IDE will use custom fonts if you place them in a `fonts/` folder next to the script:

```
fonts/DOSfont.ttf        (used in the code editor)
fonts/CascadiaMono.ttf   (used in the console)
```

If either file is missing the IDE falls back to Kivy's built-in Roboto font automatically.
No error is raised and the IDE works normally either way.

A custom window icon can be placed at:

```
ico/pyasmide.ico
```

---

## Running Without Kivy

If Kivy is not installed, running the script prints a warning and then executes the built-in demo program in the terminal:

```
============================================================
  Kivy is NOT installed.
  Install with:  pip install kivy
  Running headless demo instead...
============================================================
```

This is useful for testing the virtual machine on its own or in environments where a display is not available.

---

## Example Program

```
// Compute the sum of 1 through 5 and print it

var total = 0
append reg1 1

define add_next
  add reg2 total reg1
  var total = reg2
  reg1+1
end

[ call add_next ]5

out 'Sum of 1 to 5:'
out total
```

Expected output:

```
Sum of 1 to 5:
15
```
