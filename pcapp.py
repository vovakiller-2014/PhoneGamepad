# Phone Gamepad - PC app (needs the ViGEmBus driver)
import asyncio, colorsys, ctypes, json, os, random, socket, sys, threading, time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from aiohttp import web
import qrcode
from PIL import ImageTk

PORT = 8080
TYPES = ['Xbox 360', 'PlayStation (DS4)']
APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / 'PhoneGamepad'
APP_DIR.mkdir(parents=True, exist_ok=True)
CFG = APP_DIR / 'settings.json'
cfg = {'pin': str(random.randint(100000, 999999)), 'types': [TYPES[0]] * 8, 'lang': 'en'}
try: cfg.update(json.loads(CFG.read_text()))
except Exception: pass
cfg['types'] = (list(cfg['types']) + [TYPES[0]] * 8)[:8]
def save(): CFG.write_text(json.dumps(cfg))
save()

TX = {
 'gp': ('Gamepads', 'Геймпади'), 'free': ('○ free', '○ вільно'), 'kick': ('Disconnect', 'Відключити'),
 'hint': ('Type changes apply on the next phone connection', 'Тип змінюється при наступному підключенні телефона'),
 'bts': ('Bluetooth (incoming COM port) - experimental', 'Bluetooth (вхідний COM-порт) - експериментально'),
 'listen': ('Listen', 'Слухати'), 'reset': ('Reset', 'Скинути'),
 'nobt': ('No COM ports added', 'COM-порти не додано'), 'lis': ('Listening: ', 'Слухає: '),
 'nopy': ('pyserial not found', 'pyserial не знайдено'), 'newpin': ('New PIN', 'Новий PIN'),
 'tv': ('Test vibration', 'Тест вібрації'),
 'addr': ('Refresh address', 'Оновити адресу'),
 'btt': ('Bluetooth is experimental', 'Bluetooth ще не допрацьований'),
 'btb': ('This mode is unfinished and may disconnect.\n\n1. Pair the phone with this PC in Windows Settings > Bluetooth.\n2. Create an incoming COM port: More Bluetooth settings > COM Ports > Add > Incoming.\n3. Select that port here and press Listen, then connect from the phone app (Connect > Bluetooth).\n\nWi-Fi is the recommended way. Continue?',
         'Цей режим ще не допрацьований і може розривати зʼєднання.\n\n1. Спаруй телефон із ПК у налаштуваннях Windows > Bluetooth.\n2. Створи вхідний COM-порт: Інші параметри Bluetooth > COM-порти > Додати > Вхідний.\n3. Обери цей порт тут і натисни «Слухати», потім підключись з додатка на телефоні (Підключення > Bluetooth).\n\nРекомендується Wi-Fi. Продовжити?'),
 'drv': ('Could not create the gamepad. Is the ViGEmBus driver installed?', 'Не вдалося створити геймпад. Чи встановлено драйвер ViGEmBus?'),
 'srv': ('Server did not start (is port 8080 busy?)', 'Сервер не запустився (порт 8080 зайнятий?)'),
}
def tr(k): return TX[k][0 if cfg['lang'] == 'en' else 1]

try:
    import vgamepad as vg
except Exception as e:
    _r = tk.Tk(); _r.withdraw()
    messagebox.showerror('Phone Gamepad', tr('drv') + '\n\n' + str(e))
    sys.exit(1)
try:
    import serial, serial.tools.list_ports as lp
except Exception:
    serial = lp = None

B = vg.XUSB_BUTTON
XB = {'A': B.XUSB_GAMEPAD_A, 'B': B.XUSB_GAMEPAD_B, 'X': B.XUSB_GAMEPAD_X, 'Y': B.XUSB_GAMEPAD_Y,
      'LB': B.XUSB_GAMEPAD_LEFT_SHOULDER, 'RB': B.XUSB_GAMEPAD_RIGHT_SHOULDER,
      'BACK': B.XUSB_GAMEPAD_BACK, 'START': B.XUSB_GAMEPAD_START,
      'LS': B.XUSB_GAMEPAD_LEFT_THUMB, 'RS': B.XUSB_GAMEPAD_RIGHT_THUMB,
      'UP': B.XUSB_GAMEPAD_DPAD_UP, 'DOWN': B.XUSB_GAMEPAD_DPAD_DOWN,
      'LEFT': B.XUSB_GAMEPAD_DPAD_LEFT, 'RIGHT': B.XUSB_GAMEPAD_DPAD_RIGHT}
D = vg.DS4_BUTTONS
DS = {'A': D.DS4_BUTTON_CROSS, 'B': D.DS4_BUTTON_CIRCLE, 'X': D.DS4_BUTTON_SQUARE, 'Y': D.DS4_BUTTON_TRIANGLE,
      'LB': D.DS4_BUTTON_SHOULDER_LEFT, 'RB': D.DS4_BUTTON_SHOULDER_RIGHT,
      'BACK': D.DS4_BUTTON_SHARE, 'START': D.DS4_BUTTON_OPTIONS,
      'LS': D.DS4_BUTTON_THUMB_LEFT, 'RS': D.DS4_BUTTON_THUMB_RIGHT}
DIRS = {(0, -1): 'NORTH', (1, -1): 'NORTHEAST', (1, 0): 'EAST', (1, 1): 'SOUTHEAST', (0, 1): 'SOUTH',
        (-1, 1): 'SOUTHWEST', (-1, 0): 'WEST', (-1, -1): 'NORTHWEST', (0, 0): 'NONE'}

# ---- keyboard injection (scan codes, for gearboxes) ----
VKN = {'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27, 'space': 0x20, 'enter': 0x0D, 'tab': 0x09,
       'esc': 0x1B, 'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'backspace': 0x08}
for _i in range(10): VKN[f'num{_i}'] = 0x60 + _i
for _i in range(1, 13): VKN[f'f{_i}'] = 0x6F + _i
EXT = {0x26, 0x28, 0x25, 0x27}
class _KI(ctypes.Structure):
    _fields_ = [('wVk', ctypes.c_ushort), ('wScan', ctypes.c_ushort), ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class _MI(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong),
                ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class _U(ctypes.Union): _fields_ = [('ki', _KI), ('mi', _MI)]
class _INP(ctypes.Structure): _fields_ = [('type', ctypes.c_ulong), ('u', _U)]

def key_event(name, down):
    try:
        u = ctypes.windll.user32; n = str(name).strip().lower()
        vk = VKN.get(n)
        if vk is None and len(n) == 1: vk = u.VkKeyScanW(ord(n)) & 0xFF
        if not vk or vk == 0xFF: return
        sc = u.MapVirtualKeyW(vk, 0)
        fl = 0x8 | (0 if down else 0x2) | (0x1 if vk in EXT else 0)
        inp = _INP(1, _U(ki=_KI(0, sc, fl, 0, None)))
        u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    except Exception: pass

class Slot:
    def __init__(s): s.pad = None; s.ws = None; s.ip = ''; s.ds = False; s.dp = set(); s.keys = set(); s.cb = None
slots = [Slot() for _ in range(8)]
LOOP, ERR = [], []
LOCK = threading.Lock()
BT = set(cfg.get('bt', []))

def apply(sl, d):
    t, k, pad = d['t'], d.get('k', ''), sl.pad
    if t == 'k':
        (sl.keys.add if d['v'] else sl.keys.discard)(k); key_event(k, d['v']); return
    if t == 'b':
        if sl.ds and k in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            (sl.dp.add if d['v'] else sl.dp.discard)(k)
            dx = ('RIGHT' in sl.dp) - ('LEFT' in sl.dp); dy = ('DOWN' in sl.dp) - ('UP' in sl.dp)
            pad.directional_pad(getattr(vg.DS4_DPAD_DIRECTIONS, 'DS4_BUTTON_DPAD_' + DIRS[(dx, dy)]))
        else:
            m = (DS if sl.ds else XB)[k]
            (pad.press_button if d['v'] else pad.release_button)(m)
    elif t == 's':
        f = pad.left_joystick_float if k == 'L' else pad.right_joystick_float
        f(d['x'], d['y'] if sl.ds else -d['y'])
    elif t == 'tr':
        (pad.left_trigger_float if k == 'LT' else pad.right_trigger_float)(d['v'])
    pad.update()

def reg_rumble(sl):
    def cb(client, target, large, small, extra, user_data):
        try:
            if sl.ws and LOOP:
                asyncio.run_coroutine_threadsafe(sl.ws.send_str(json.dumps({'t': 'rb', 'l': int(large), 's': int(small)})), LOOP[0])
        except Exception: pass
    sl.cb = cb
    try: sl.pad.register_notification(cb)
    except Exception: pass

def acquire(label):
    with LOCK:
        i = next((n for n, x in enumerate(slots) if x.pad is None), None)
        if i is None: return None
        sl = slots[i]; sl.ds = cfg['types'][i] == TYPES[1]; sl.dp = set(); sl.keys = set()
        try: sl.pad = vg.VDS4Gamepad() if sl.ds else vg.VX360Gamepad()
        except Exception as e:
            ERR.append(tr('drv') + '\n' + str(e)); return None
        sl.ip = label; return sl

def release(sl):
    for k in list(sl.keys): key_event(k, False)
    sl.keys.clear()
    pad, sl.pad, sl.ws = sl.pad, None, None
    try: pad.unregister_notification()
    except Exception: pass
    del pad

async def ws_h(req):
    s = web.WebSocketResponse(heartbeat=15); await s.prepare(req)
    if req.query.get('pin') != cfg['pin']:
        await s.close(message=b'pin'); return s
    sl = acquire(req.remote)
    if sl is None:
        await s.close(message=b'full'); return s
    sl.ws = s; reg_rumble(sl)
    try:
        async for m in s:
            if m.type == web.WSMsgType.TEXT:
                try: apply(sl, json.loads(m.data))
                except Exception: pass
    finally:
        release(sl)
    return s

async def index(_):
    for p in (Path(sys.executable).parent / 'index.html', Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'index.html'):
        if p.exists(): return web.FileResponse(p)
    return web.Response(text='index.html not found', status=404)

def run_server():
    async def main():
        app = web.Application(); app.add_routes([web.get('/', index), web.get('/ws', ws_h)])
        r = web.AppRunner(app); await r.setup()
        await web.TCPSite(r, '0.0.0.0', PORT).start()
        await asyncio.Event().wait()
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); LOOP.append(loop)
    try: loop.run_until_complete(main())
    except Exception as e: ERR.append(tr('srv') + '\n' + str(e))

def blog(msg):
    try:
        with open(APP_DIR / 'bt.log', 'a', encoding='utf-8') as f: f.write(time.strftime('%H:%M:%S ') + msg + '\n')
    except Exception: pass

def bt_reader(port):
    while port in BT:
        try: ser = serial.Serial(port, 115200, timeout=1)
        except Exception as e:
            blog(f'open fail {port}: {e}'); time.sleep(2); continue
        blog(f'open ok {port}')
        sl, last, buf, errs = None, 0, b'', 0
        while port in BT:
            try: data = ser.read(512); errs = 0
            except Exception as e:
                errs += 1; blog(f'read err {errs}: {e}')
                if errs > 20: break
                time.sleep(0.5); continue
            now = time.time()
            if data:
                buf += data; last = now
                *lines, buf = buf.split(b'\n')
                for ln in lines:
                    if not ln.strip(): continue
                    if sl is None:
                        sl = acquire('BT ' + port); blog(f'phone connected, slot={sl is not None}')
                    if sl is None: continue
                    try: apply(sl, json.loads(ln))
                    except Exception as e: blog(f'apply err: {e}')
            elif sl is not None and now - last > 4:
                blog('no data 4s, release'); release(sl); sl = None
        if sl is not None: release(sl)
        blog(f'close {port}')
        try: ser.close()
        except Exception: pass

def local_ip():
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); c.connect(('8.8.8.8', 80)); return c.getsockname()[0]
    except Exception: return '127.0.0.1'

# ---------------- GUI ----------------
BG, FG, DIM, GREEN = '#000000', '#dddddd', '#666666', '#2ecc71'
root = tk.Tk(); root.title('Phone Gamepad'); root.configure(bg=BG); root.resizable(False, False)
cv = tk.Canvas(root, bg=BG, highlightthickness=0); cv.pack()
body = tk.Frame(cv, bg=BG)
left = tk.Frame(body, bg=BG); left.grid(row=0, column=0, padx=24, pady=20, sticky='n')
right = tk.Frame(body, bg=BG); right.grid(row=0, column=1, padx=(0, 24), pady=20, sticky='n')
REG = []
def reg(w, key): REG.append((w, key)); w.config(text=tr(key)); return w
def mkbtn(parent, key, cmd, **kw):
    return reg(tk.Button(parent, command=cmd, bg=BG, fg=FG, relief='solid', bd=1, activebackground='#222', activeforeground=FG, **kw), key)

qr_lbl = tk.Label(left, bg=BG); qr_lbl.pack()
pin_lbl = tk.Label(left, bg=BG, fg=FG, font=('Segoe UI', 22, 'bold')); pin_lbl.pack(pady=(10, 0))
url_lbl = tk.Label(left, bg=BG, fg=DIM, font=('Segoe UI', 9)); url_lbl.pack()
qr_img = None

def draw():
    global qr_img
    url = f'http://{local_ip()}:{PORT}/?pin={cfg["pin"]}'
    q = qrcode.QRCode(box_size=8, border=2); q.add_data(url); q.make(fit=True)
    qr_img = ImageTk.PhotoImage(q.make_image(fill_color='black', back_color='white').get_image().convert('RGB'))
    qr_lbl.config(image=qr_img); pin_lbl.config(text='PIN ' + cfg['pin']); url_lbl.config(text=url)
def new_pin():
    cfg['pin'] = str(random.randint(100000, 999999)); save(); draw()

mkbtn(left, 'addr', draw, padx=10).pack(pady=(8, 0), fill='x')
def test_rumble():
    def go(l, s):
        for sl in slots:
            if sl.ws and LOOP:
                asyncio.run_coroutine_threadsafe(sl.ws.send_str(json.dumps({'t': 'rb', 'l': l, 's': s})), LOOP[0])
    go(200, 200); root.after(600, lambda: go(0, 0))
mkbtn(left, 'newpin', new_pin, padx=10).pack(pady=(6, 0), fill='x')
mkbtn(left, 'tv', test_rumble, padx=10).pack(pady=(6, 0), fill='x')
lang_btn = tk.Button(left, bg=BG, fg=FG, relief='solid', bd=1, padx=10, activebackground='#222', activeforeground=FG)
lang_btn.pack(pady=(6, 0), fill='x')

title = reg(tk.Label(right, bg=BG, fg=FG, font=('Segoe UI', 16, 'bold')), 'gp'); title.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 8))
rows = []
def kick(i):
    if slots[i].ws and LOOP: asyncio.run_coroutine_threadsafe(slots[i].ws.close(), LOOP[0])
def set_type(i, v): cfg['types'][i] = v.get(); save()
for i in range(8):
    tk.Label(right, text=f'{i+1}', bg=BG, fg=DIM, width=2).grid(row=i+1, column=0, pady=3)
    st = tk.Label(right, text='', bg=BG, fg=DIM, width=18, anchor='w'); st.grid(row=i+1, column=1)
    v = tk.StringVar(value=cfg['types'][i])
    cb = ttk.Combobox(right, textvariable=v, values=TYPES, state='readonly', width=17); cb.grid(row=i+1, column=2, padx=6)
    cb.bind('<<ComboboxSelected>>', lambda e, i=i, v=v: set_type(i, v))
    kb = mkbtn(right, 'kick', lambda i=i: kick(i), state='disabled'); kb.grid(row=i+1, column=3)
    rows.append((st, kb))
reg(tk.Label(right, bg=BG, fg=DIM, font=('Segoe UI', 8)), 'hint').grid(row=9, column=0, columnspan=4, sticky='w', pady=(8, 0))

def refresh_ports():
    bt_cb['values'] = [f'{p.device} - {p.description}' for p in lp.comports()] if lp else []
def bt_show():
    bt_lbl.config(text=tr('nopy') if not serial else (tr('lis') + ', '.join(sorted(BT)) if BT else tr('nobt')))
def bt_add():
    port = bt_var.get().split(' ')[0]
    if not port or not serial or port in BT: return
    if not messagebox.askokcancel(tr('btt'), tr('btb')): return
    BT.add(port); cfg['bt'] = sorted(BT); save(); bt_show()
    threading.Thread(target=bt_reader, args=(port,), daemon=True).start()
def bt_clear():
    BT.clear(); cfg['bt'] = []; save(); bt_show()
reg(tk.Label(right, bg=BG, fg=FG, font=('Segoe UI', 11, 'bold')), 'bts').grid(row=10, column=0, columnspan=4, sticky='w', pady=(14, 4))
bt_var = tk.StringVar()
bt_cb = ttk.Combobox(right, textvariable=bt_var, state='readonly', width=44, postcommand=refresh_ports); bt_cb.grid(row=11, column=0, columnspan=3, sticky='w')
mkbtn(right, 'listen', bt_add).grid(row=11, column=3)
bt_lbl = tk.Label(right, bg=BG, fg=DIM, font=('Segoe UI', 9)); bt_lbl.grid(row=12, column=0, columnspan=3, sticky='w', pady=(4, 0))
mkbtn(right, 'reset', bt_clear).grid(row=12, column=3, pady=(4, 0))

# RGB glow around the window
G = {'ids': [], 'off': 0.0, 'N': 200}
def glow():
    root.update_idletasks()
    W, H = body.winfo_reqwidth() + 28, body.winfo_reqheight() + 28
    cv.config(width=W, height=H); cv.delete('glow')
    if not cv.find_withtag('win'): cv.create_window(14, 14, window=body, anchor='nw', tags='win')
    w, h = W - 8, H - 8; per = 2 * (w + h)
    def pt(s):
        s %= per
        if s < w: return 4 + s, 4
        s -= w
        if s < h: return 4 + w, 4 + s
        s -= h
        if s < w: return 4 + w - s, 4 + h
        s -= w; return 4, 4 + h - s
    N = G['N']; G['ids'] = []
    for i in range(N):
        a, b = pt(per * i / N), pt(per * (i + 1) / N + 1)
        G['ids'].append(cv.create_line(*a, *b, width=4, capstyle='round', tags='glow'))
def glow_tick():
    G['off'] = (G['off'] + 0.006) % 1; N = G['N']
    for i, it in enumerate(G['ids']):
        r, g, b = colorsys.hsv_to_rgb((i / N + G['off']) % 1, 0.8, 1)
        cv.itemconfig(it, fill='#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255)))
    root.after(50, glow_tick)

def relang():
    for w, k in REG: w.config(text=tr(k))
    lang_btn.config(text='UA' if cfg['lang'] == 'en' else 'EN'); bt_show(); glow()
def toggle_lang():
    cfg['lang'] = 'ua' if cfg['lang'] == 'en' else 'en'; save(); relang()
lang_btn.config(command=toggle_lang)

def refresh():
    for sl, (st, kb) in zip(slots, rows):
        on = sl.pad is not None
        st.config(text=('● ' + sl.ip) if on else tr('free'), fg=GREEN if on else DIM)
        kb.config(state='normal' if on else 'disabled')
    if ERR: messagebox.showerror('Phone Gamepad', ERR.pop(0))
    root.after(500, refresh)

for _p in list(BT):
    if serial: threading.Thread(target=bt_reader, args=(_p,), daemon=True).start()
threading.Thread(target=run_server, daemon=True).start()
draw(); relang(); glow_tick(); refresh(); root.mainloop()
