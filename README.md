# Blender-Maze-Generator
A comprehensive Maze generator for Blender 4.1+

**Description:**
The Maze Generator is a Blender add-on designed to create customizable, random maze meshes within Blender. This tool is ideal for users in game development, architectural visualization, or artistic projects who need to quickly generate complex mazes with various configurations.

**Features:**
Random Maze Generation: Generate mazes with customizable dimensions and properties. Users can adjust parameters such as rows, columns, cell size, and wall height to vary the complexity and size of the maze.

**Solidify Modifier:** Optionally apply a solidify modifier to give thickness to maze walls, enhancing the 3D appearance.
**Solidify Thickness:** Optionally adjust the solidify modifier wall thickness.
**Bevel Modifier:** Optionally apply a bevel modifier to smooth out the edges of the maze walls, providing a more polished look.
**Advanced Configuration Options:** Includes settings for random seed input, allowing users to reproduce specific mazes consistently. Additional controls for deleting isolated sections ("islands") of the maze and adjusting the complexity through iterations.
**Real-time Updates:** Adjust maze parameters in real-time from the Blender UI, with immediate visual feedback in the 3D view.
**Floor & Ceiling:** Optionally generate a floor plane at the base of the maze and a ceiling at wall height. Each is created as its own object (`Maze_Floor`, `Maze_Ceiling`) so you can assign materials or delete them independently.
**Boundary Walls:** Optionally enclose the maze in an outer wall frame (`Maze_Boundary`), pushed out from the maze edge by an adjustable number of cells, turning the maze into a self-contained room. Boundary thickness uses a live solidify modifier so it stays adjustable after generation.
**Entrance & Exit:** Optionally cut entrance and exit openings into the boundary to define start and end areas. Each opening is placed by choosing a wall (North / South / East / West) and a position along it (0 = corner, 0.5 = centre, 1 = opposite corner), so you can make anything from diagonally opposite corner doors to a straight shot through (e.g. West-centre entrance + East-centre exit). Width is adjustable, and both openings may even share a wall. (Openings mark start/end areas; a guaranteed solvable path between them is not enforced.)
**Randomise Entrance / Randomise Exit:** Two one-click buttons that move the chosen door to the wall opposite the other door and pick a random position along it. Because only the boundary depends on the door positions, they rebuild just the boundary wall and leave the maze, floor and ceiling untouched — so they stay instant even on large mazes. Press repeatedly to shuffle a door until you like it.

**How to Use:**
1. 1Install the add-on in Blender.
2. 2Navigate to the Sidebar > Create tab in the 3D View.
3. 3Adjust the maze parameters in the Maze Generator panel located at the bottom left of the viewport:
Rows and Columns: Adjust the subdivision level of the grid on the X and Y axis to control the number of walls.
Cell Size: Modifies the overall size of the maze.
Wall Height: Controls the height of the maze walls.
Environment Options: At the bottom of the panel, optionally add a floor, a ceiling, and a boundary wall frame. Boundary Offset controls how far (in cells) the frame is pushed out from the maze. Cut Entrance/Exit with Door Width enables the start/end openings, and Entrance/Exit Side plus Entrance/Exit Position place each opening on a chosen wall. The Randomise Entrance and Randomise Exit buttons shuffle a door to a random spot on the wall opposite the other door and rebuild the boundary instantly.
4. 4Click the "Generate Maze" button to create new mazes with your current settings.
5. 5Further customize the generated maze by modifying materials or applying additional Blender modifiers for enhanced visual effects.


**Compatibility:**
Blender 4.2+ (Untested on earlier versions)


**Testing:**
The Blender-independent logic (the maze algorithm and the boundary geometry
math) is covered by a small unit-test suite that stubs out Blender, so it runs
in a plain Python interpreter with no Blender or extra packages required:

```
python tests/test_maze_generator.py
```

Everything that drives `bpy` / `bmesh` is only exercisable inside Blender and is
intentionally out of scope for these tests.

**Author:**
Lee Shaw


**Version:**
0.3.1


**License:**
This add-on is released under an open-source license: GNU GENERAL PUBLIC LICENSE - Version 3, 29 June 2007. Please refer to the license file for more information.


**Disclaimer:**
The Maze Generator add-on is provided as-is, without any warranties or guarantees. Use it at your own risk. Generating an extremely large Maze could cause blender to crash.


**Support:**
For any issues, suggestions, or feedback, please feel free to contact the author or report them on the add-on's GitHub repository.


**GitHub Repository:**
https://github.com/ljsau/Blender-Maze-Generator
Enjoy exploring your mazes with the Maze Generator add-on!
