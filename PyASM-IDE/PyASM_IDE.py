"""
PyASM IDE - Python Assembly Language Interpreter
Full Virtual Machine with Kivy UI

Run:
    pip install kivy
    python pyasm_ide.py

Font setup (optional):
    Place custom fonts in a  fonts/  folder next to this script:
        fonts/DOSfont.ttf       <- editor font
        fonts/CascadiaMono.ttf  <- console font
    If missing, Kivy's built-in Roboto is used automatically.

Without Kivy installed the script falls back to a headless demo.
"""

import os
import re
import sys


def resource_path(relative_path):
    """Works both normally and inside a PyInstaller bundle."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


# ═══════════════════════════════════════════════════════════════════════════
#  VIRTUAL MACHINE  (pure Python – zero external dependencies)
# ═══════════════════════════════════════════════════════════════════════════

class PyASMError(Exception):
    def __init__(self, kind, msg):
        super().__init__(f"[{kind}] {msg}")
        self.kind = kind
        self.msg  = msg


class VirtualMachine:
    NUM_REGS = 16

    def __init__(self, output_cb=None, input_cb=None):
        self.output_cb = output_cb or print
        self.input_cb  = input_cb
        self.reset()

    def reset(self):
        self.registers = {f"reg{i}": [] for i in range(1, self.NUM_REGS + 1)}
        self.variables = {}
        self.functions = {}
        self.pc        = 0
        self.program   = []
        self._halted   = False

    def load(self, source: str):
        self.reset()
        self.program = self._preprocess(source.splitlines())

    def _strip_comment(self, line: str) -> str:
        idx = line.find("//")
        return line[:idx].strip() if idx != -1 else line.strip()

    def _preprocess(self, raw_lines):
        cleaned = [self._strip_comment(l) for l in raw_lines]
        cleaned = [l for l in cleaned if l]
        executable = []
        i = 0
        while i < len(cleaned):
            line = cleaned[i]
            if line.startswith("define "):
                fname = line[7:].strip()
                body  = []
                i += 1
                while i < len(cleaned) and cleaned[i].strip() != "end":
                    body.append(cleaned[i])
                    i += 1
                self.functions[fname] = body
                i += 1
            else:
                executable.append(line)
                i += 1
        return executable

    def run(self):
        while not self._halted and self.pc < len(self.program):
            self._exec_line(self.program[self.pc])
            if not self._halted:
                self.pc += 1

    def step(self):
        if self._halted or self.pc >= len(self.program):
            return False
        self._exec_line(self.program[self.pc])
        if not self._halted:
            self.pc += 1
        return True

    def is_done(self):
        return self._halted or self.pc >= len(self.program)

    def _exec_line(self, line: str):
        line = line.strip()
        if not line or line == "skip":
            return
        if line == "exit":
            self._halted = True
            return
        if re.fullmatch(r"\[.*\]\d*", line, re.DOTALL):
            self._exec_loop_block(line)
            return
        inc_dec = re.fullmatch(r"(reg\d+)([+\-])(\d+)", line)
        if inc_dec:
            self._op_incdec(inc_dec.group(1), inc_dec.group(2),
                            int(inc_dec.group(3)))
            return
        parts = line.split()
        op    = parts[0].lower()
        dispatch = {
            "var":    self._op_var,
            "mov":    self._op_mov,
            "append": self._op_append,
            "add":    self._op_add,
            "sub":    self._op_sub,
            "mul":    self._op_mul,
            "div":    self._op_div,
            "xchg":   self._op_xchg,
            "cmp":    self._op_cmp,
            "out":    self._op_out,
            "input":  self._op_input,
            "call":   self._op_call,
        }
        if op in dispatch:
            dispatch[op](parts)
        else:
            raise PyASMError("Syntax Error", f"Unknown instruction: '{line}'")

    def _exec_loop_block(self, line):
        m = re.fullmatch(r"\[(.*)\](\d*)", line, re.DOTALL)
        if not m:
            raise PyASMError("Syntax Error", f"Malformed loop: {line}")
        count      = int(m.group(2)) if m.group(2) else 1
        body_lines = [l.strip() for l in m.group(1).split(";") if l.strip()]
        for _ in range(count):
            for bl in body_lines:
                self._exec_line(bl)
                if self._halted:
                    return

    def _valid_reg(self, name):
        if name not in self.registers:
            raise PyASMError("Register Name Error",
                             f"'{name}' is not a valid register (reg1-reg{self.NUM_REGS})")
        return name

    def _resolve_value(self, token):
        if token in self.registers:
            r = self.registers[token]
            if not r:
                raise PyASMError("Undefined Value Error",
                                 f"Register '{token}' is empty")
            return r[-1]
        if token in self.variables:
            v = self.variables[token]
            try:
                return int(v)
            except (ValueError, TypeError):
                return v
        try:
            return int(token, 16) if token.startswith(("0x", "0X")) else int(token)
        except ValueError:
            raise PyASMError("Undefined Value Error",
                             f"Cannot resolve value: '{token}'")

    def _op_var(self, parts):
        if len(parts) < 4 or parts[2] != "=":
            raise PyASMError("Syntax Error", "Usage: var <n> = <value>")
        token = " ".join(parts[3:])
        if (token.startswith("'") and token.endswith("'")) or \
           (token.startswith('"') and token.endswith('"')):
            self.variables[parts[1]] = token[1:-1]
        else:
            self.variables[parts[1]] = self._resolve_value(token)

    def _op_mov(self, parts):
        if len(parts) != 3:
            raise PyASMError("Syntax Error", "Usage: mov regDst regSrc")
        dst, src = self._valid_reg(parts[1]), self._valid_reg(parts[2])
        self.registers[dst] = self.registers[src][:]
        self.registers[src] = []

    def _op_append(self, parts):
        if len(parts) != 3:
            raise PyASMError("Syntax Error", "Usage: append regX value")
        self.registers[self._valid_reg(parts[1])].append(
            self._resolve_value(parts[2]))

    def _op_add(self, parts):
        if len(parts) != 4:
            raise PyASMError("Syntax Error", "Usage: add regD regA regB")
        self.registers[self._valid_reg(parts[1])].append(
            self._resolve_value(parts[2]) + self._resolve_value(parts[3]))

    def _op_sub(self, parts):
        if len(parts) != 4:
            raise PyASMError("Syntax Error", "Usage: sub regD regA regB")
        self.registers[self._valid_reg(parts[1])].append(
            self._resolve_value(parts[2]) - self._resolve_value(parts[3]))

    def _op_mul(self, parts):
        if len(parts) != 4:
            raise PyASMError("Syntax Error", "Usage: mul regD regA regB")
        self.registers[self._valid_reg(parts[1])].append(
            self._resolve_value(parts[2]) * self._resolve_value(parts[3]))

    def _op_div(self, parts):
        if len(parts) != 4:
            raise PyASMError("Syntax Error", "Usage: div regD regA regB")
        b = self._resolve_value(parts[3])
        if b == 0:
            raise PyASMError("Undefined Value Error", "Division by zero")
        self.registers[self._valid_reg(parts[1])].append(
            self._resolve_value(parts[2]) // b)

    def _op_xchg(self, parts):
        if len(parts) != 3:
            raise PyASMError("Syntax Error", "Usage: xchg regA regB")
        a, b = self._valid_reg(parts[1]), self._valid_reg(parts[2])
        self.registers[a], self.registers[b] = self.registers[b], self.registers[a]

    def _op_cmp(self, parts):
        if len(parts) != 4:
            raise PyASMError("Syntax Error", "Usage: cmp regD regA regB")
        self.registers[self._valid_reg(parts[1])].append(
            1 if self._resolve_value(parts[2]) >= self._resolve_value(parts[3]) else 0)

    def _op_out(self, parts):
        target = " ".join(parts[1:])
        if (target.startswith("'") and target.endswith("'")) or \
           (target.startswith('"') and target.endswith('"')):
            self.output_cb(target[1:-1])
            return
        if target in self.registers:
            self.output_cb(str(self.registers[target]))
            return
        if target in self.variables:
            self.output_cb(str(self.variables[target]))
            return
        raise PyASMError("Undefined Value Error",
                         f"'out' target '{target}' not found")

    def _op_input(self, parts):
        raw      = " ".join(parts[1:])
        m        = re.match(r'["\'](.+?)["\']', raw)
        prompt   = m.group(1) if m else "Input"
        reg_name = parts[-1]
        self._valid_reg(reg_name)
        user_in = self.input_cb(prompt) if self.input_cb else input(f"{prompt}: ")
        try:
            val = int(user_in, 16)
        except ValueError:
            try:
                val = int(user_in)
            except ValueError:
                raise PyASMError("Undefined Value Error",
                                 f"Input '{user_in}' is not valid hex/int")
        self.registers[reg_name].append(val)

    def _op_call(self, parts):
        if len(parts) != 2:
            raise PyASMError("Syntax Error", "Usage: call <n>")
        fname = parts[1]
        if fname not in self.functions:
            raise PyASMError("Undefined Value Error",
                             f"Undefined function '{fname}'")
        for fline in self.functions[fname]:
            self._exec_line(fline)
            if self._halted:
                return

    def _op_incdec(self, reg, op, n):
        self._valid_reg(reg)
        if not self.registers[reg]:
            raise PyASMError("Undefined Value Error",
                             f"Register '{reg}' is empty")
        if op == "+":
            self.registers[reg][-1] += n
        else:
            self.registers[reg][-1] -= n


# ═══════════════════════════════════════════════════════════════════════════
#  CONTENT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

DEMO_PROGRAM = """\
// PyASM Demo Program
// Demonstrates: vars, registers, loops, functions, output

var greeting = 'Hello from PyASM!'
out greeting

// Push values into reg1 and reg2
append reg1 5
append reg2 3

// Add reg1[-1] + reg2[-1] -> reg3
add reg3 reg1 reg2
out 'reg1[-1] + reg2[-1] stored in reg3:'
out reg3

// Loop: increment reg3 top value 4 times (2 iters x 2 increments)
[ reg3+1; reg3+1 ]2
out 'After 4 increments via loop:'
out reg3

// Define and call a function
define show_regs
  out 'reg1:'
  out reg1
  out 'reg2:'
  out reg2
  out 'reg3:'
  out reg3
end

call show_regs

// Compare
cmp reg4 reg3 reg1
out 'cmp reg3 >= reg1 -> reg4:'
out reg4

var counter = 42
out counter
out 'Done!'
"""

HELP_TEXT = """\
[b][color=33aaff]PyASM Quick Reference[/color][/b]

[b]Variables[/b]
  var <n> = <value>

[b]Registers[/b]  reg1-reg16 (each is a list; ops use last element)
  append regX <val>       push value onto register
  mov    regDst regSrc    move all (src cleared)
  xchg   regA regB        swap entire contents
  regX+N  /  regX-N       inc / dec last element

[b]Arithmetic[/b]  (result appended to regD)
  add / sub / mul / div   regD regA regB

[b]Compare[/b]
  cmp regD regA regB      1 if regA[-1] >= regB[-1], else 0

[b]I/O[/b]
  out <reg | varname | 'string'>
  input "prompt" regX     hex or int input

[b]Functions[/b]
  define <n>
    ...instructions...
  end
  call <n>

[b]Loops[/b]  (separate instructions with ; inside brackets)
  [ instr1; instr2 ]N     repeat N times

[b]Control[/b]
  exit    halt
  skip    no-op

[b]Comments[/b]
  // anything after // is ignored

[b]Files[/b]  saved to  ~/Python Assembly Files/*.pyasm
"""

SAVE_DIR = os.path.join(os.path.expanduser("~"), "Python Assembly Files")


# ═══════════════════════════════════════════════════════════════════════════
#  KIVY UI
# ═══════════════════════════════════════════════════════════════════════════
KIVY_AVAILABLE = False

try:
    import kivy
    kivy.require("2.0.0")

    from kivy.app              import App
    from kivy.uix.boxlayout    import BoxLayout
    from kivy.uix.gridlayout   import GridLayout
    from kivy.uix.scrollview   import ScrollView
    from kivy.uix.label        import Label
    from kivy.uix.button       import Button
    from kivy.uix.textinput    import TextInput
    from kivy.uix.popup        import Popup
    from kivy.uix.filechooser  import FileChooserListView
    from kivy.core.window      import Window
    from kivy.core.text        import LabelBase   # ← needed for font registration
    from kivy.graphics         import Color, Rectangle, RoundedRectangle
    from kivy.clock            import Clock
    from kivy.metrics          import dp

    KIVY_AVAILABLE = True

    # ── palette ───────────────────────────────────────────────────────────
    BG_DARK   = (0.07, 0.07, 0.10, 1)
    BG_PANEL  = (0.11, 0.11, 0.15, 1)
    BG_EDITOR = (0.09, 0.09, 0.12, 1)
    ACCENT    = (0.20, 0.65, 1.00, 1)
    ACCENT2   = (0.10, 0.85, 0.55, 1)
    TEXT_MAIN = (0.90, 0.92, 0.95, 1)
    TEXT_DIM  = (0.50, 0.52, 0.56, 1)
    REG_BG    = (0.14, 0.14, 0.20, 1)
    BTN_RUN   = (0.10, 0.75, 0.40, 1)
    BTN_STEP  = (0.15, 0.50, 0.90, 1)
    BTN_STOP  = (0.85, 0.25, 0.25, 1)
    BTN_NEW   = (0.25, 0.25, 0.35, 1)
    BTN_FILE  = (0.20, 0.20, 0.30, 1)

    # ── font registration ─────────────────────────────────────────────────
    # Kivy requires fonts to be registered via LabelBase.register() before
    # they can be referenced by a short name in font_name=.
    # If the .ttf files are absent we fall back to Kivy's built-in "Roboto".
    # The resolved names (FONT_EDITOR / FONT_CONSOLE) are safe to use
    # in any widget regardless of whether the custom files exist.

    def _try_register(name: str, ttf_relative: str) -> str:
        """
        Try to register a custom TTF.
        Returns the registered name on success, or 'Roboto' on failure.
        """
        path = resource_path(ttf_relative)
        if os.path.isfile(path):
            try:
                LabelBase.register(name, path)
                return name
            except Exception as exc:
                print(f"[PyASM] Warning: could not register font '{name}' "
                      f"from '{path}': {exc}")
        else:
            print(f"[PyASM] Warning: font file not found: '{path}' "
                  f"-- falling back to Roboto")
        return "Roboto"

    FONT_EDITOR  = _try_register("DOSfont",      os.path.join("fonts", "DOSfont.ttf"))
    FONT_CONSOLE = _try_register("CascadiaMono", os.path.join("fonts", "CascadiaMono.ttf"))

    # ── helper ────────────────────────────────────────────────────────────
    def _make_btn(text, bg, color=None, bold=True, fs=13):
        return Button(
            text=text, bold=bold,
            font_size=dp(fs),
            background_normal="",
            background_color=bg,
            color=color or TEXT_MAIN,
            size_hint_y=None,
            height=dp(36),
        )

    # ── RegisterBox ───────────────────────────────────────────────────────
    class RegisterBox(BoxLayout):
        def __init__(self, reg_name, **kw):
            super().__init__(
                orientation="vertical",
                size_hint=(None, None),
                size=(dp(90), dp(54)),
                padding=dp(3),
                spacing=dp(1),
                **kw,
            )
            self.reg_name = reg_name
            with self.canvas.before:
                Color(*REG_BG)
                self._bg = RoundedRectangle(
                    pos=self.pos, size=self.size, radius=[dp(4)])
            self.bind(pos=self._upd, size=self._upd)
            self.lbl_name = Label(
                text=reg_name, font_size=dp(10), bold=True,
                color=ACCENT, size_hint_y=None, height=dp(16))
            self.lbl_val = Label(
                text="[ ]", font_size=dp(9), color=TEXT_MAIN,
                halign="center", valign="middle",
                text_size=(dp(85), None))
            self.add_widget(self.lbl_name)
            self.add_widget(self.lbl_val)

        def _upd(self, *_):
            self._bg.pos  = self.pos
            self._bg.size = self.size

        def update(self, values):
            txt = str(values) if values else "[ ]"
            self.lbl_val.text = txt[:12] + "..." if len(txt) > 13 else txt

    # ── PyASMIDE ─────────────────────────────────────────────────────────
    class PyASMIDE(BoxLayout):
        def __init__(self, **kw):
            super().__init__(orientation="vertical",
                             spacing=dp(4), padding=dp(6), **kw)
            self.vm = VirtualMachine(
                output_cb=self._vm_output,
                input_cb=self._vm_input,
            )
            with self.canvas.before:
                Color(*BG_DARK)
                self._bg = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=self._upd, size=self._upd)
            self._build_toolbar()
            self._build_body()
            self._build_registers()

        def _upd(self, *_):
            self._bg.pos  = self.pos
            self._bg.size = self.size

        # toolbar ──────────────────────────────────────────────────────────
        def _build_toolbar(self):
            bar = BoxLayout(size_hint_y=None, height=dp(44),
                            spacing=dp(4), padding=(0, dp(4), 0, dp(4)))
            with bar.canvas.before:
                Color(*BG_PANEL)
                self._tb = Rectangle(pos=bar.pos, size=bar.size)
            bar.bind(pos=lambda *_: setattr(self._tb, "pos",  bar.pos),
                     size=lambda *_: setattr(self._tb, "size", bar.size))

            bar.add_widget(Label(
                text="  PyASM IDE", bold=True, font_size=dp(15),
                color=ACCENT, size_hint_x=None, width=dp(120)))

            buttons = [
                ("+ New File",        BTN_NEW,  self._on_new),
                ("Save File",         BTN_FILE, self._on_save),
                ("Load File",         BTN_FILE, self._on_load),
                ("Step",              BTN_STEP, self._on_step),
                ("Run",               BTN_RUN,  self._on_run),
                ("Reset Registers",   BTN_STOP, self._on_reset),
                ("Help",              BTN_NEW,  self._on_help),
            ]
            for label, bg, handler in buttons:
                b = _make_btn(label, bg)
                b.bind(on_press=handler)
                bar.add_widget(b)

            self.add_widget(bar)

        # editor + console ─────────────────────────────────────────────────
        def _build_body(self):
            body = BoxLayout(spacing=dp(6), size_hint_y=0.62)

            # left: editor
            left = BoxLayout(orientation="vertical", spacing=dp(4))
            hdr_e = Label(
                text="  Code Editor", bold=True, font_size=dp(16),
                color=ACCENT, size_hint_y=None, height=dp(22), halign="left")
            hdr_e.bind(size=hdr_e.setter("text_size"))
            self.editor = TextInput(
                font_size=dp(17),
                font_name=FONT_EDITOR,      # registered name or "Roboto"
                background_color=BG_EDITOR,
                foreground_color=TEXT_MAIN,
                cursor_color=ACCENT,
                hint_text="// Write PyASM code here...",
                hint_text_color=TEXT_DIM,
                text=DEMO_PROGRAM,
            )
            left.add_widget(hdr_e)
            left.add_widget(self.editor)

            # right: console
            right = BoxLayout(orientation="vertical", spacing=dp(4))
            hdr_c = BoxLayout(size_hint_y=None, height=dp(22))
            lbl_c = Label(
                text="  Console Output", bold=True, font_size=dp(16),
                color=ACCENT2, halign="left")
            lbl_c.bind(size=lbl_c.setter("text_size"))
            btn_clr = Button(
                text="Clear Console Output", font_size=dp(13),
                background_normal="", background_color=BTN_NEW,
                color=TEXT_MAIN, size_hint_x=None, width=dp(180))
            btn_clr.bind(on_press=lambda *_: self._clear_console())
            hdr_c.add_widget(lbl_c)
            hdr_c.add_widget(btn_clr)

            self._con_sv = ScrollView()
            self.console = TextInput(
                font_size=dp(17),
                font_name=FONT_CONSOLE,     # registered name or "Roboto"
                background_color=BG_PANEL,
                foreground_color=TEXT_MAIN,
                readonly=True,
                hint_text="Output appears here...",
                hint_text_color=TEXT_DIM,
            )
            self._con_sv.add_widget(self.console)

            self.lbl_pc = Label(
                text="PC: 0  |  Status: IDLE",
                font_size=dp(13), color=TEXT_DIM,
                size_hint_y=None, height=dp(25), halign="left")
            self.lbl_pc.bind(size=self.lbl_pc.setter("text_size"))

            right.add_widget(hdr_c)
            right.add_widget(self._con_sv)
            right.add_widget(self.lbl_pc)

            body.add_widget(left)
            body.add_widget(right)
            self.add_widget(body)

        # register panel ───────────────────────────────────────────────────
        def _build_registers(self):
            wrap = BoxLayout(orientation="vertical",
                             size_hint_y=None, height=dp(128), spacing=dp(2))
            lbl = Label(
                text="  Registers", bold=True, font_size=dp(16),
                color=ACCENT, size_hint_y=None, height=dp(18), halign="left")
            lbl.bind(size=lbl.setter("text_size"))

            sv   = ScrollView(do_scroll_y=False)
            grid = GridLayout(rows=2, spacing=dp(4), padding=dp(4),
                              size_hint_x=None)
            grid.bind(minimum_width=grid.setter("width"))

            self.reg_boxes = {}
            for i in range(1, self.vm.NUM_REGS + 1):
                rname = f"reg{i}"
                box   = RegisterBox(rname)
                self.reg_boxes[rname] = box
                grid.add_widget(box)

            sv.add_widget(grid)
            wrap.add_widget(lbl)
            wrap.add_widget(sv)
            self.add_widget(wrap)

        # VM callbacks ─────────────────────────────────────────────────────
        def _vm_output(self, text):
            self.console.text += text + "\n"
            Clock.schedule_once(
                lambda dt: setattr(self._con_sv, "scroll_y", 0), 0.05)

        def _vm_input(self, prompt):
            import time
            result = ["0"]
            done   = [False]

            layout = BoxLayout(orientation="vertical",
                               padding=dp(12), spacing=dp(8))
            layout.add_widget(Label(text=prompt, color=TEXT_MAIN,
                                    font_size=dp(14)))
            ti = TextInput(
                hint_text="Enter hex or integer",
                multiline=False, font_size=dp(14),
                background_color=BG_EDITOR, foreground_color=TEXT_MAIN,
                size_hint_y=None, height=dp(40))
            layout.add_widget(ti)

            def _ok(*_):
                result[0] = ti.text or "0"
                done[0]   = True
                pop.dismiss()

            ok_btn = _make_btn("OK", BTN_RUN)
            ok_btn.bind(on_press=_ok)
            ti.bind(on_text_validate=_ok)
            layout.add_widget(ok_btn)

            pop = Popup(title="Input Required", content=layout,
                        size_hint=(0.45, 0.30),
                        background_color=BG_PANEL)
            pop.open()
            while not done[0]:
                Clock.tick()
                time.sleep(0.02)
            return result[0]

        # toolbar actions ──────────────────────────────────────────────────
        def _on_new(self, *_):
            self.editor.text  = ""
            self.console.text = ""
            self.vm.reset()
            self._refresh_regs()
            self._set_status("IDLE")

        def _on_reset(self, *_):
            self.vm.reset()
            self._refresh_regs()
            self._set_status("RESET")

        def _on_run(self, *_):
            self.console.text = ""
            try:
                self.vm.load(self.editor.text)
                self.vm.run()
                self._refresh_regs()
                self._set_status("DONE")
            except PyASMError as e:
                self._vm_output(f"ERROR ({e.kind}): {e.msg}")
                self._set_status("ERROR")
            except Exception as e:
                self._vm_output(f"INTERNAL ERROR: {e}")
                self._set_status("ERROR")

        def _on_step(self, *_):
            if not self.vm.program and not self.vm._halted:
                try:
                    self.vm.load(self.editor.text)
                    self.console.text = ""
                except PyASMError as e:
                    self._vm_output(f"ERROR ({e.kind}): {e.msg}")
                    self._set_status("ERROR")
                    return
            if self.vm.is_done():
                self._vm_output("-- Program finished --")
                self._set_status("DONE")
                return
            try:
                self.vm.step()
                self._refresh_regs()
                self._set_status(f"STEP  line {self.vm.pc}")
            except PyASMError as e:
                self._vm_output(f"ERROR ({e.kind}): {e.msg}")
                self._set_status("ERROR")

        def _on_save(self, *_):
            os.makedirs(SAVE_DIR, exist_ok=True)
            layout = BoxLayout(orientation="vertical",
                               padding=dp(10), spacing=dp(8))
            layout.add_widget(Label(
                text=f"Save to:\n{SAVE_DIR}",
                color=TEXT_MAIN, font_size=dp(12)))
            ti = TextInput(
                hint_text="filename (no extension)",
                multiline=False, font_size=dp(13),
                background_color=BG_EDITOR, foreground_color=TEXT_MAIN,
                size_hint_y=None, height=dp(36))
            layout.add_widget(ti)

            def _do(*_):
                fname = ti.text.strip()
                if fname:
                    path = os.path.join(SAVE_DIR, fname + ".pyasm")
                    with open(path, "w") as f:
                        f.write(self.editor.text)
                    self._vm_output(f"Saved -> {path}")
                pop.dismiss()

            btn = _make_btn("Save", BTN_RUN)
            btn.bind(on_press=_do)
            ti.bind(on_text_validate=_do)
            layout.add_widget(btn)
            pop = Popup(title="Save File", content=layout,
                        size_hint=(0.5, 0.30),
                        background_color=BG_PANEL)
            pop.open()

        def _on_load(self, *_):
            os.makedirs(SAVE_DIR, exist_ok=True)
            fc = FileChooserListView(path=SAVE_DIR, filters=["*.pyasm"])
            layout = BoxLayout(orientation="vertical", spacing=dp(6))
            layout.add_widget(fc)

            def _do(*_):
                if fc.selection:
                    with open(fc.selection[0], "r") as f:
                        self.editor.text = f.read()
                    self._vm_output(f"Loaded <- {fc.selection[0]}")
                    pop.dismiss()

            bb  = BoxLayout(size_hint_y=None, height=dp(40))
            btn = _make_btn("Open", BTN_RUN)
            btn.bind(on_press=_do)
            bb.add_widget(btn)
            layout.add_widget(bb)
            pop = Popup(title="Load .pyasm File", content=layout,
                        size_hint=(0.65, 0.70),
                        background_color=BG_PANEL)
            pop.open()

        def _on_help(self, *_):
            sv  = ScrollView()
            lbl = Label(
                text=HELP_TEXT, markup=True,
                font_size=dp(12), color=TEXT_MAIN,
                size_hint_y=None, halign="left",
                text_size=(Window.width * 0.58, None))
            lbl.bind(texture_size=lbl.setter("size"))
            sv.add_widget(lbl)
            Popup(title="PyASM Quick Reference", content=sv,
                  size_hint=(0.65, 0.80),
                  background_color=BG_PANEL).open()

        # util ─────────────────────────────────────────────────────────────
        def _refresh_regs(self):
            for rname, box in self.reg_boxes.items():
                box.update(self.vm.registers[rname])

        def _set_status(self, status):
            self.lbl_pc.text = (
                f"PC: {self.vm.pc}  |  {status}"
                f"  |  Vars: {len(self.vm.variables)}"
                f"  |  Fns: {len(self.vm.functions)}"
            )

        def _clear_console(self):
            self.console.text = ""

    # ── App ───────────────────────────────────────────────────────────────
    class PyASMApp(App):
        def build(self):
            # Set icon only if the file actually exists (avoids crash)
            ico = resource_path(os.path.join("ico", "pyasmide.ico"))
            if os.path.isfile(ico):
                Window.set_icon(ico)
            Window.clearcolor     = BG_DARK
            Window.title          = "Python Assembly - PyASM IDE"
            Window.minimum_width  = 800
            Window.minimum_height = 560
            return PyASMIDE()

except ImportError:
    pass   # KIVY_AVAILABLE stays False


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if KIVY_AVAILABLE:
        PyASMApp().run()
    else:
        print("=" * 60)
        print("  Kivy is NOT installed.")
        print("  Install with:  pip install kivy")
        print("  Running headless demo instead...")
        print("=" * 60)
        output = []
        vm = VirtualMachine(output_cb=lambda t: output.append(t))
        vm.load(DEMO_PROGRAM)
        vm.run()
        print("\n--- OUTPUT ---")
        print("\n".join(output))
        print("\n--- REGISTERS (non-empty) ---")
        for r, v in vm.registers.items():
            if v:
                print(f"  {r}: {v}")
        print("\n--- VARIABLES ---")
        for k, v in vm.variables.items():
            print(f"  {k} = {v!r}")


if __name__ == "__main__":
    main()