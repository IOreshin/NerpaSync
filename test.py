
sdgd = 'wegnrofs\\sdgf\\sdfg.das'

parts = sdgd.split('\\')

path = '\\'.join(parts[:-1])

name = parts[-1][:-4]

print(name)

