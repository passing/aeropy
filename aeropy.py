#!/usr/bin/python3

class Color:
	def __init__(self, red, green, blue):
		self.red = red
		self.green = green
		self.blue = blue
	def __str__(self):
		return f'{self.red}, {self.green}, {self.blue}'
	def __add__(self, other):
		return Color(self.red + other.red, self.green + other.green, self.blue + other.blue)
	def __mul__(self, other):
		return Color(self.red * other, self.green * other, self.blue * other)
	def __eq__(self, other):
		return (self.red == other.red and self.green == other.green and self.blue == other.blue)
	def __round__(self):
		return Color(round(self.red), round(self.green), round(self.blue))


class LightObject:
	def __init__(self):
		self.duration = 0;
	def get_duration(self):
		return self.duration
	def commands(self):
		return []
	def render(self):
		return []


class LightComment(LightObject):
	def __init__(self, value):
		super().__init__()
		self.value = value;
	def commands(self):
		return [f';{self.value}']


class LightCommand(LightObject):
	def __init__(self, color_start, color_end, duration):
		self.color_start = color_start
		self.color_end = color_end
		self.duration = duration
	def __eq__(self, other):
		return (self.color_start == other.color_start and self.color_end == other.color_end and self.duration == other.duration)
	def commands(self):
		commands = []
		commands.append(f'C, {self.color_start}')
		if (self.color_end == self.color_start):
			commands.append(f'D, {self.duration}')
		else:
			commands.append(f'RAMP, {self.color_end}, {self.duration}')
		return commands
	def render(self):
		colors = []
		for n in range(self.duration):
			colors.append(round(self.color_start * (1 - (n / self.duration)) + self.color_end * (n / self.duration)))
		return colors


class LightProgram(LightObject):
	def __init__(self, objects):
		self.objects = objects
	def get_duration(self):
		return sum(object.get_duration() for object in self.objects)
	def commands(self):
		commands = []
		for o in self.objects:
			commands.extend(o.commands())
		return commands
	def render(self):
		colors = []
		for o in self.objects:
			colors.extend(o.render())
		return colors



class LightSubProgram(LightProgram):
	def __init__(self, name, objects):
		super().__init__(objects)
		self.name = name
	def commands(self):
		return [f'SUB, {self.name}']



class LightLoop(LightObject):
	def __init__(self, program, count):
		self.program = program
		self.count = count
	def get_duration(self):
		return self.count * self.program.get_duration()
	def commands(self):
		commands = []
		commands.append(f'L, {self.count}')
		commands.extend(self.program.commands())
		commands.append('E')
		return commands
	def render(self):
		colors = []
		for n in range(self.count):
			colors.extend(self.program.render())
		return colors


x = LightCommand(color_start=Color(1,2,3), color_end=Color(1,2,3), duration=2)
print(x.get_duration())
print(x.color_start)
print(x.color_start * 10)
print(x.color_end)
for color in x.render():
	print(color)
print()

y = LightCommand(color_start=Color(0,0,0), color_end=Color(2,20,30), duration=3)
print(y.get_duration())
print(y.color_start)
print(y.color_end)
for color in y.render():
	print(color)
for command in y.commands():
	print(command)
print()

p = LightSubProgram(name="test", objects=[x, y])
print(p.get_duration())
for color in p.render():
	print(color)
print()

l = LightLoop(program=p, count=2)
print(l.get_duration())
for color in l.render():
	print(color)
print()

ll = LightLoop(program=l, count=2)

c = LightComment("hello")

p2 = LightProgram([p, c, ll])
print (p2.get_duration())
for command in p2.commands():
	print(command)
for color in p2.render():
	print(color)
print()
