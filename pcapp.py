# Phone Gamepad — програма для ПК (потрібен драйвер ViGEmBus)
import asyncio, json, os, random, socket, sys, threading, time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from aiohttp import web
import qrcode
from PIL import ImageTk
try:
    import vgamepad as vg
except Exception as e:
    _r = tk.Tk(); _r.withdraw()
    messagebox.showerror('Phone Gamepad', 'Не вдалося запустити геймпад. Чи встановлено драйвер ViGEmBus?\n\n' + str(e))
    sys.exit(1)

PORT = 8080
TYPES = ['Xbox 360', 'PlayStation (DS4)']
APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / 'PhoneGamepad'
APP_DIR.mkdir(parents=True, exist_ok=True)
CFG = APP_DIR / 'settings.json'
cfg = {'pin': str(random.randint(100000, 999999)), 'types': [TYPES[0]] * 8}
try: cfg.update(json.loads(CFG.read_text()))
except Exception: pass
cfg['types'] = (list(cfg['types']) + [TYPES[0]] * 8)[:8]
def save(): CFG.write_text(json.dumps(cfg))
save()

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

class Slot:
    def __init__(s): s.pad = None; s.ws = None; s.ip = ''; s.ds = False; s.dp = set()
slots = [Slot() for _ in range(8)]
LOOP, ERR = [], []
LOCK = threading.Lock()
try:
    import serial, serial.tools.list_ports as lp
except Exception:
    serial = lp = None
BT = set(cfg.get('bt', []))

def acquire(label):
    with LOCK:
        i = next((n for n, x in enumerate(slots) if x.pad is None), None)
        if i is None: return None
        sl = slots[i]; sl.ds = cfg['types'][i] == TYPES[1]; sl.dp = set()
        try: sl.pad = vg.VDS4Gamepad() if sl.ds else vg.VX360Gamepad()
        except Exception as e:
            ERR.append('Не вдалося створити геймпад.\n' + str(e)); return None
        sl.ip = label; return sl

def release(sl):
    pad, sl.pad, sl.ws = sl.pad, None, None; del pad

def bt_reader(port):
    while port in BT:
        try: ser = serial.Serial(port, 115200, timeout=1)
        except Exception: time.sleep(2); continue
        sl, last, buf = None, 0, b''
        while port in BT:
            try: data = ser.read(512)
            except Exception: break
            now = time.time()
            if data:
                buf += data; last = now
                *lines, buf = buf.split(b'\n')
                for ln in lines:
                    if not ln.strip(): continue
                    if sl is None: sl = acquire('BT ' + port)
                    if sl is None: continue
                    try: apply(sl, json.loads(ln))
                    except Exception: pass
            elif sl is not None and now - last > 4:
                release(sl); sl = None
        if sl is not None: release(sl)
        try: ser.close()
        except Exception: pass

def apply(sl, d):
    t, k, pad = d['t'], d['k'], sl.pad
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

async def ws_h(req):
    s = web.WebSocketResponse(heartbeat=15); await s.prepare(req)
    if req.query.get('pin') != cfg['pin']:
        await s.close(message=b'pin'); return s
    i = next((n for n, x in enumerate(slots) if x.pad is None), None)
    if i is None:
        await s.close(message=b'full'); return s
    sl = slots[i]; sl.ds = cfg['types'][i] == TYPES[1]; sl.dp = set()
    try: sl.pad = vg.VDS4Gamepad() if sl.ds else vg.VX360Gamepad()
    except Exception as e:
        ERR.append('Не вдалося створити геймпад. Встановлено ViGEmBus?\n' + str(e)); await s.close(); return s
    sl.ws, sl.ip = s, req.remote
    try:
        async for m in s:
            if m.type == web.WSMsgType.TEXT:
                try: apply(sl, json.loads(m.data))
                except Exception: pass
    finally:
        pad, sl.pad, sl.ws = sl.pad, None, None; del pad
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
    except Exception as e: ERR.append(f'Сервер не запустився (порт {PORT} зайнятий?)\n{e}')

def local_ip():
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); c.connect(('8.8.8.8', 80)); return c.getsockname()[0]
    except Exception: return '127.0.0.1'

BG, FG, DIM, GREEN = '#000000', '#dddddd', '#666666', '#2ecc71'
root = tk.Tk(); root.title('Phone Gamepad'); root.configure(bg=BG); root.resizable(False, False)
left = tk.Frame(root, bg=BG); left.grid(row=0, column=0, padx=24, pady=20, sticky='n')
right = tk.Frame(root, bg=BG); right.grid(row=0, column=1, padx=(0, 24), pady=20, sticky='n')
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

for txt, cmd in (('Оновити адресу', draw), ('Новий PIN', new_pin)):
    tk.Button(left, text=txt, command=cmd, bg=BG, fg=FG, relief='solid', bd=1, padx=10).pack(pady=(8, 0), fill='x')

tk.Label(right, text='Геймпади', bg=BG, fg=FG, font=('Segoe UI', 16, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 8))
rows = []
def kick(i):
    if slots[i].ws and LOOP: asyncio.run_coroutine_threadsafe(slots[i].ws.close(), LOOP[0])
def set_type(i, v):
    cfg['types'][i] = v.get(); save()
for i in range(8):
    tk.Label(right, text=f'{i+1}', bg=BG, fg=DIM, width=2).grid(row=i+1, column=0, pady=3)
    st = tk.Label(right, text='○ вільно', bg=BG, fg=DIM, width=18, anchor='w'); st.grid(row=i+1, column=1)
    v = tk.StringVar(value=cfg['types'][i])
    cb = ttk.Combobox(right, textvariable=v, values=TYPES, state='readonly', width=17); cb.grid(row=i+1, column=2, padx=6)
    cb.bind('<<ComboboxSelected>>', lambda e, i=i, v=v: set_type(i, v))
    kb = tk.Button(right, text='Відключити', command=lambda i=i: kick(i), bg=BG, fg=FG, relief='solid', bd=1, state='disabled')
    kb.grid(row=i+1, column=3)
    rows.append((st, kb))
tk.Label(right, text='Тип змінюється при наступному підключенні телефона', bg=BG, fg=DIM, font=('Segoe UI', 8)).grid(row=9, column=0, columnspan=4, sticky='w', pady=(8, 0))

def refresh_ports():
    bt_cb['values'] = [f'{p.device} — {p.description}' for p in lp.comports()] if lp else []
def bt_show():
    bt_lbl.config(text=('pyserial не знайдено' if not serial else ('Слухає: ' + ', '.join(sorted(BT)) if BT else 'COM-порти не додано')))
def bt_add():
    port = bt_var.get().split(' ')[0]
    if not port or not serial or port in BT: return
    BT.add(port); cfg['bt'] = sorted(BT); save(); bt_show()
    threading.Thread(target=bt_reader, args=(port,), daemon=True).start()
def bt_clear():
    BT.clear(); cfg['bt'] = []; save(); bt_show()
tk.Label(right, text='Bluetooth (вхідний COM-порт)', bg=BG, fg=FG, font=('Segoe UI', 11, 'bold')).grid(row=10, column=0, columnspan=4, sticky='w', pady=(14, 4))
bt_var = tk.StringVar()
bt_cb = ttk.Combobox(right, textvariable=bt_var, state='readonly', width=44, postcommand=refresh_ports); bt_cb.grid(row=11, column=0, columnspan=3, sticky='w')
tk.Button(right, text='Слухати', command=bt_add, bg=BG, fg=FG, relief='solid', bd=1).grid(row=11, column=3)
bt_lbl = tk.Label(right, bg=BG, fg=DIM, font=('Segoe UI', 9)); bt_lbl.grid(row=12, column=0, columnspan=3, sticky='w', pady=(4, 0))
tk.Button(right, text='Скинути', command=bt_clear, bg=BG, fg=FG, relief='solid', bd=1).grid(row=12, column=3, pady=(4, 0))
bt_show()

def refresh():
    for sl, (st, kb) in zip(slots, rows):
        on = sl.pad is not None
        st.config(text=('● ' + sl.ip) if on else '○ вільно', fg=GREEN if on else DIM)
        kb.config(state='normal' if on else 'disabled')
    if ERR:
        messagebox.showerror('Phone Gamepad', ERR.pop(0))
    root.after(500, refresh)

for _p in list(BT):
    if serial: threading.Thread(target=bt_reader, args=(_p,), daemon=True).start()
threading.Thread(target=run_server, daemon=True).start()
draw(); refresh(); root.mainloop()
