# aeropy

Script simplifying programming of glowing juggling props from aerotech. http://www.aerotechprojects.com

## feature overview

### importing

* import glo files (old & new syntax)
* merge multiple glo files
* split file for multiple props
* import PNG images

### processing

* align to audacity labels
* resolve unsupported parameters
* resolve constants
* strip comments
* compress sequences

### exporting

* write glo files with variable syntax
* render png image
* render video (uses ffmpeg) with audio

## features

### merging multiple files

arguments:
```
-input FILE1 FILE2 FILE3
```

Multiple glo files will be merged so that the light sequences of all files run in the order of the files.
Conflicts are pervented by prefixing all constants and sub-routines.
For aligning the sequences of each file it makes sense to use audacity labels.

### multiple props conditons

arguments:
```
-input FILE -number 3
```

Use the conditions like in the example below to obtain certain parts to be valid only for certain props.

*example to make clubs 1 & 3 red, club 2 blue and all others green*
```
<1,3>
color (255, 0, 0)
<2>
color (0, 0, 255)
<default>
color (0, 255, 0)
<end>
end
```

### png import

arguments:
```
-import-png FILE [-import-png-ramps]
```

Import a png file (that has no alpha channel).  
A sequence is created from each row of the image. Each pixel in that row sets the color for a hundredth second.
E.g. an image with width = 500 and height = 3 will result in 3 sequences of 5 seconds.

The `-import-png-ramps` option results in `ramp` commands to be created instead of `color` and `delay` commands.
That is useful for importing images with smooth transitions in combination with the `-compress` option.

### align sequences to audacity labels

arguments:
```
-input FILE -labels FILE
```

labels file:
```
7.000000        7.000000        a
10.000000       10.000000       b
```
glo file:
```
time (set, 500)
color (255, 0, 0)

time (set, label, a, +5)
color (0, 0, 255)

time (setref, label, b, -5)

time (set, 500)
color (255, 0, 0)

time (set, label, a, -5)
color (0, 0, 255)
delay (500)

time (setref, 0)

end
```
result:
```
; TIME SHIFT (set, 500): time=0, target=0+500+0, add=500
delay (500)
color (255, 0, 0)

; TIME SHIFT (set, label, a, 5): time=500, target=0+700+5, add=205
delay (205)
color (0, 0, 255)

; TIME REFERENCE (setref, label, b, -5): old=0, new=1000-5

; TIME SHIFT (set, 500): time=705, target=995+500+0, add=790
delay (790)
color (255, 0, 0)

; TIME SHIFT (set, label, a, -5): time=1495, target=995+700-5, add=195
delay (195)
color (0, 0, 255)
delay (500)

; TIME REFERENCE (setref, 0): old=995, new=0+0

end
```

### resolve unsupported parameters

arguments:
```
-unsupported
```

- delays longer than 65535 hundredth seconds get split
- loops repeating zero times get removed (including their content)
- loops repeating one time get removed (leaving their content)
- loops repeating more than 255 times are converted to nested loops (resulting in the same number of repetitions)

### resolve constants

arguments:
```
- resolve
```

resolves all constants in the output

### strip comments

arguments:
```
-strip
```

removes all empty lines and comments in the output

### sequence compression

arguments:
```
-compress
```

#### repetition compression

Identified repetitions are turned into loops and sub-sequences.
The resulting light sequences are identical to the original ones.

### ramp compression

arguments:
```
-epsilon [0.0 - 255]
```

Subsequent ramps are merged using the [Douglas-Peucker algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm).
The algorithm ensures that the distance from the resulting light sequence to the original one is within a defined range.

The `-epsilon` options defines the maximum distance of the compressed sequence to the original sequence at any point in time.
Setting it to a higher value causes a higher compression ratio as it allows for bigger color changes.
The distance between two colors is defined as the length of their direct connection in an RGB cube.
The biggest possible distance between two colors is 442 (from black to white, red to cyan, green to magenta or blue to yellow).

### glo file export

arguments:
```
-output BASENAME [-syntax {legacy,british,camel,call}] [-tab SPACES]
```

Write sequences to numbered files.
You can choose different command sets/variants using `-syntax`.
Use `-tab` to configure the number of spaces used for indention (set to 0 to disable).

### image and video rendering

arguments:
```
-amplify
```

The `-amplify` option causes color components to be amplified in the rendered image or video (using sqrt function).
Colors with a low lightness will get brighter, which trying to simulate their actual visual perception.

#### png export

arguments:
```
-png FILE [-png-resolution RESOLUTION] [-png-stretch STRETCH] [-png-padding PADDING]
```

The light sequences get rendered to an image file.
Time spans from left to the right with each pixel column representing `-png-resolution` hundredth seconds.  
Each sequence results in a horizontal bar.
In each bar, pixels from `-png-resolution` hundredth seconds are put into the same pixel column, one below the other.
The resulting image can be stretched vertically using the `-png-stretch` option.  
The `-png-padding` option controls the space between the bars.

#### video rendering

the script creates a video (using ffmpeg), simulating the exact time flow of the light sequences.

dependencies:
- ffmpeg
- libx264
- libvo_aacenc

arguments:
```
-video FILE 
[-video-audio FILE] 
[-video-fps FPS] 
[-video-start-seconds SECONDS] 
[-video-width WIDTH] 
[-video-height HEIGHT] 
[-video-window WINDOW] 
[-video-bar-width WIDTH] 
[-video-preset {slow,medium,fast,faster,veryfast,superfast,ultrafast}]
```

The light sequences get rendered as a video with one vertical bar for each sequence.
In each frame, the colors of `-video-window` hundredth seconds will be drawn one above the other.
Setting `-video-window` to 1 will cause just one color to be shown at a time in each bar.
Choosing a higher value like 200 (2 seconds) will result in a nice panning effect.

Use the `-video-audio` option to let ffmpeg copy an mp3 file into the resulting video.
You can choose to start rendering at a defined time with the `-video-start-seconds` option.

