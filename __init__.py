# ----------------------------------------------------------------------------#
#                                    LICENCE                                  #
# ----------------------------------------------------------------------------#
#   Copyright (C) <2025>  <Lee Shaw>
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


# ----------------------------------------------------------------------------#
#                               ADDON DESCRIPTION                             #
# ----------------------------------------------------------------------------#


bl_info = {
    "name": "Maze Generator",
    "blender": (4, 2, 0),
    "category": "Object",
    "author": "Lee Shaw",
    "version": (0, 3, 0),
    "location": "View3D > Sidebar > Create",
    "description": "Generates a random maze mesh",
    "warning": "",
    "wiki_url": "https://github.com/ljsau/Blender-Maze-Generator/blob/main/README.md",
    "tracker_url": "https://github.com/ljsau/Blender-Maze-Generator/issues",
}


# ----------------------------------------------------------------------------#
#                                 BLENDER IMPORT                              #
# ----------------------------------------------------------------------------#


import bpy
import random
import bmesh
import time
from mathutils import Vector


# ----------------------------------------------------------------------------#
#                                    CONSTANTS                                #
# ----------------------------------------------------------------------------#


OGM = "object.generate_maze"


#   Boundary wall sides, shared by the entrance and exit side selectors.
#   The parenthetical axes map onto the user's mental model: West = -X,
#   East = +X, South = -Y, North = +Y.
_SIDE_ITEMS = [
    ("NORTH", "North", "North wall (+Y)"),
    ("SOUTH", "South", "South wall (-Y)"),
    ("EAST", "East", "East wall (+X)"),
    ("WEST", "West", "West wall (-X)"),
]


#   Map each wall to the wall facing it, used by the "Randomise Exit" button.
_OPPOSITE_SIDE = {
    "NORTH": "SOUTH",
    "SOUTH": "NORTH",
    "EAST": "WEST",
    "WEST": "EAST",
}


# ----------------------------------------------------------------------------#
#                                    CLASS: VERTEX                            #
# ----------------------------------------------------------------------------#
#   Represents a single vertex in the maze grid.

#   Attributes:
#       row (int): Row index of the vertex in the grid.
#       col (int): Column index of the vertex.
#       direction (Vertex): Optional; points to another vertex
#       to establish a path in the maze.

#   The `direction` attribute is used to trace the path from
#   one vertex to another, forming the corridors of the maze.


class Vertex:
    def __init__(self, row, col):
        self.row = row  # Row index of the vertex in the grid or graph
        self.col = col  # Column index of the vertex in the grid or graph
        self.direction = None  # Direction associated with the vertex


# ----------------------------------------------------------------------------#
#                         CLASS: OBJECT_OT_GenerateMaze                       #
# ----------------------------------------------------------------------------#
#   Blender operator to generate a maze. It handles user inputs,
#   maze generation, and updates the 3D view.


class OBJECT_OT_GenerateMaze(bpy.types.Operator):
    bl_idname = "object.generate_maze"
    bl_label = "Generate Maze"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Generate a maze with customizable parameters"

    #   Create adjustable properties for the user, accessible from the
    #   3D Viewport's bottom left after initial maze generation.
    #   Dragging these values modifies the maze in real-time.
    #   later in the script we will integrate these properties
    #   into the Create Menu side panel, where changes will apply
    #   post 'Generate Maze' button press, benefiting users with
    #   slower PCs or when generating large, laggy mazes.

    random_seed: bpy.props.IntProperty(
        name="Random Seed",
        default=0,
        description="Seed value for random maze generation",
    )

    rows: bpy.props.IntProperty(
        name="Rows", default=20, min=1, description="Number of rows in the maze grid"
    )

    columns: bpy.props.IntProperty(
        name="Columns",
        default=20,
        min=1,
        description="Number of columns in the maze grid",
    )

    cell_size: bpy.props.IntProperty(
        name="Cell Size", default=2, min=1, description="Size of each maze cell (XY)"
    )

    wall_height: bpy.props.FloatProperty(
        name="Wall Height",
        default=2.4,
        min=0.01,
        description="Height of the maze walls",
    )

    iterations: bpy.props.IntProperty(
        name="Iterations",
        default=5,
        min=1,
        description="Number of iterations for maze generation algorithm",
    )

    delete_islands: bpy.props.BoolProperty(
        name="Delete Islands",
        default=True,
        description="Whether to delete isolated areas of the maze",
    )

    wall_count: bpy.props.IntProperty(
        name="Island Wall Count",
        default=6,
        min=0,
        description="Determines the quantity of walls that will be removed",
    )

    apply_solidify: bpy.props.BoolProperty(
        name="Apply Solidify",
        default=True,
        description="Whether to apply the solidify modifier to the maze walls",
    )

    wall_thickness: bpy.props.FloatProperty(  # type: ignore
        name="Wall Thickness",
        default=0.15,
        min=0.01,
        max=1.0,
        description="Thickness of the maze walls",
    )

    apply_bevel: bpy.props.BoolProperty(
        name="Apply Bevel",
        default=True,
        description="Whether to apply the bevel modifier to the maze walls",
    )

    #   Environment options. These build optional extra objects (floor,
    #   ceiling, boundary frame) around the finished maze. They default to
    #   off so that, unless the user opts in, the generated maze is identical
    #   to previous versions.

    add_floor: bpy.props.BoolProperty(
        name="Add Floor",
        default=False,
        description="Add a floor plane at the base of the maze (separate object)",
    )

    add_ceiling: bpy.props.BoolProperty(
        name="Add Ceiling",
        default=False,
        description="Add a ceiling plane at the top of the maze (separate object)",
    )

    add_boundary: bpy.props.BoolProperty(
        name="Add Boundary Walls",
        default=False,
        description="Add an outer wall frame enclosing the maze (separate object)",
    )

    boundary_offset: bpy.props.IntProperty(
        name="Boundary Offset",
        default=1,
        min=0,
        description="How far to push the boundary walls out from the maze, in cells",
    )

    add_doors: bpy.props.BoolProperty(
        name="Cut Entrance/Exit",
        default=True,
        description="Cut entrance and exit gaps in the boundary, at opposite corners",
    )

    door_width: bpy.props.IntProperty(
        name="Door Width",
        default=1,
        min=1,
        description="Width of the entrance/exit gaps, in cells",
    )

    entrance_side: bpy.props.EnumProperty(
        name="Entrance Side",
        items=_SIDE_ITEMS,
        default="SOUTH",
        description="Which boundary wall the entrance opening is cut into",
    )

    entrance_position: bpy.props.FloatProperty(
        name="Entrance Position",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Position of the entrance along its wall (0 = corner, 0.5 = centre, 1 = opposite corner)",
    )

    exit_side: bpy.props.EnumProperty(
        name="Exit Side",
        items=_SIDE_ITEMS,
        default="NORTH",
        description="Which boundary wall the exit opening is cut into",
    )

    exit_position: bpy.props.FloatProperty(
        name="Exit Position",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Position of the exit along its wall (0 = corner, 0.5 = centre, 1 = opposite corner)",
    )

    # ------------------------------------------------------------------------#
    #                               DEFINE: execute                           #
    # ------------------------------------------------------------------------#
    #   Executes the maze generation process, updates the scene,
    #   and handles errors and performance timing.

    #   This method coordinates the steps involved in generating a new maze,
    #   including initializing the grid, creating the maze structure, and
    #   applying necessary modifications. It also measures the execution time
    #   for performance tracking.

    #   Parameters:
    #       context (bpy.types.Context): The context in which the operator
    #       is executed, providing access to data and area of
    #       Blender being operated on.

    #   Returns:
    #       {'FINISHED'} if the maze generation completes successfully,
    #       {'CANCELLED'} if an error occurs during the process.

    #   Raises:
    #       Exception: If any step in the maze generation process fails,
    #       an error is reported through Blender's reporting system,
    #       and the exception is re-raised to halt further execution.
    #       This ensures that partial or incorrect maze generation
    #       does not occur.

    def execute(self, context):

        try:
            time_start = time.perf_counter()
            print("Maze Generator version 0.3.0")

            #   All the real work lives in run_generation() so that the
            #   "Randomise Exit" operator can reuse it directly, instead of
            #   re-invoking this operator (nested operator calls do not apply
            #   reliably).
            run_generation(self)

            time_end = time.perf_counter()
            duration = time_end - time_start
            # Output to console
            print()
            print(f"Maze generation completed in {duration:.3f} seconds.")
            print()

        #   Rudimentary error handling.
        except Exception as e:
            self.report({"ERROR"}, f"An error occurred: {str(e)}")
            return {"CANCELLED"}
        return {"FINISHED"}


# ----------------------------------------------------------------------------#
#                              DEFINE: create_grid                            #
# ----------------------------------------------------------------------------#
#   Generates the grid layout for the maze and initializes vertices,
#   applying specified modifiers and settings.

#   This function sets up a grid of vertices based on the specified
#   number of rows and columns.
#   It initializes the maze structure by linking vertices according to
#   the maze generation algorithm.
#   The function also handles the application of Blender modifiers like
#   solidify and bevel based on user inputs,
#   and performs cleanup tasks like deleting isolated islands within the maze.

#   Parameters:
#       rows (int): Number of rows in the maze grid.
#       cols (int): Number of columns in the maze grid.
#       cell_size (int): Size of each cell in the maze (XY dimensions).
#       wall_height (float): Height of the maze walls.
#       iterations (int): Number of iterations for the maze
#                         generation algorithm.
#       delete_islands (bool): Flag to determine whether to remove
#       isolated sections of the maze.
#       island_wall_count (int): Maximum number of walls an island can have
#       before it is removed.
#       apply_solidify (bool): Flag to determine whether to apply the
#       solidify modifier to the maze walls.
#       apply_bevel (bool): Flag to determine whether to apply the bevel
#       modifier to the maze walls.


def create_grid(
    rows,
    cols,
    cell_size,
    wall_height,
    iterations,
    delete_islands,
    wall_count,
    apply_solidify,
    wall_thickness,
    apply_bevel,
):

    try:
        time_start = time.perf_counter()

        vertices = [[Vertex(row, col) for col in range(cols)] for row in range(rows)]
        initialize_maze(vertices, rows, cols)

        mesh = bpy.data.meshes.new(name="Maze")
        obj = bpy.data.objects.new(name="Maze", object_data=mesh)
        bpy.context.collection.objects.link(obj)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        verts = [
            (col * cell_size, row * cell_size, 0)
            for row in range(rows)
            for col in range(cols)
        ]

        mesh.from_pydata(verts, [], [])

        for _ in range(iterations):
            origin_row = random.randint(0, rows - 1)
            origin_col = random.randint(0, cols - 1)
            origin_vertex = vertices[origin_row][origin_col]

            neighbor_vertex = random_walk(vertices, origin_vertex, rows, cols)

            origin_vertex.direction = neighbor_vertex

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Create grid completed in {duration:.3f} seconds.")
        print()

        visualize_maze(mesh, vertices, rows, cols, cell_size)
        extrude_walls(obj, wall_height)

        if apply_solidify:
            apply_solidify_modifier(obj, apply_solidify, wall_thickness)

        if delete_islands:
            delete_more_walls(obj, delete_islands, wall_count)

        if apply_bevel:
            apply_bevel_modifier(obj, apply_bevel)

        apply_transform_and_cleanup(obj, wall_height)

    except Exception as e:
        print(f"Error in create_grid: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                             DEFINE: initialize_maze                         #
# ----------------------------------------------------------------------------#
#   Initializes the maze using a depth-first search
#   to set directions for each vertex.


def initialize_maze(vertices, rows, cols):

    try:
        time_start = time.perf_counter()

        visited = set()
        stack = [(0, 0)]
        while stack:
            row, col = stack.pop()
            visited.add((row, col))
            neighbors = [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]

            random.shuffle(neighbors)
            for neighbor_row, neighbor_col in neighbors:
                if (
                    0 <= neighbor_row < rows
                    and 0 <= neighbor_col < cols
                    and (neighbor_row, neighbor_col) not in visited
                ):
                    vertices[row][col].direction = vertices[neighbor_row][neighbor_col]
                    stack.append((neighbor_row, neighbor_col))
                    visited.add((neighbor_row, neighbor_col))

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Initialize maze completed in {duration:.3f} seconds.")
        print()

    except Exception as e:
        print(f"Error in initialize_maze: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                         DEFINE: random_walk                                 #
# ----------------------------------------------------------------------------#
#   Selects a random neighboring vertex for the
#   given vertex within the maze grid.

#   Parameters:
#       vertices (list): 2D list of Vertex objects
#       representing the maze grid.
#       vertex (Vertex): The vertex for which a
#       neighbor is to be found.
#       rows (int): Total number of rows in the maze grid.
#       cols (int): Total number of columns in the maze grid.

#   Returns:
#       Vertex: A randomly selected neighboring vertex
#       that is within grid bounds and not previously visited.

#   This function checks the four
#   possible directions (up, down, left, right)
#   from the given vertex and selects one randomly.


def random_walk(vertices, vertex, rows, cols):

    try:
        time_start = time.perf_counter()

        neighbors = []
        if vertex.row > 0:
            neighbors.append(vertices[vertex.row - 1][vertex.col])
        if vertex.row < rows - 1:
            neighbors.append(vertices[vertex.row + 1][vertex.col])
        if vertex.col > 0:
            neighbors.append(vertices[vertex.row][vertex.col - 1])
        if vertex.col < cols - 1:
            neighbors.append(vertices[vertex.row][vertex.col + 1])

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Random walk completed in {duration:.3f} seconds.")
        print()

        return random.choice(neighbors)

    except Exception as e:
        print(f"Error in random_walk: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                             DEFINE: visualize_maze                          #
# ----------------------------------------------------------------------------#
#   Creates edges between vertices in the mesh based on their directions
# to visualize the maze.

#   Parameters:
#       mesh (Mesh): The Blender mesh data block where the maze
#                   geometry is stored.
#       vertices (list): 2D list of Vertex objects
#                       representing the maze grid.
#       rows (int): Number of rows in the maze grid.
#       cols (int): Number of columns in the maze grid.
#       cell_size (float): The size of each cell in the maze.

#   This function iterates over each vertex and adds an edge
#   to the mesh for each direction that is not None,
#   effectively drawing the maze paths.


def visualize_maze(mesh, vertices, rows, cols, cell_size):

    try:
        time_start = time.perf_counter()

        edges = []
        for row in range(rows):
            for col in range(cols):
                vertex = vertices[row][col]
                if vertex.direction:
                    edges.append(
                        (
                            row * cols + col,
                            vertex.direction.row * cols + vertex.direction.col,
                        )
                    )

        mesh.edges.add(len(edges))
        mesh.edges.foreach_set("vertices", [v for e in edges for v in e])

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Visualize maze completed in {duration:.4f} seconds.")
        print()

    except Exception as e:
        print(f"Error in visualize_maze: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                               DEFINE: extrude_walls                         #
# ----------------------------------------------------------------------------#
#   Extrudes the maze's walls vertically to the specified height to
#   create a 3D maze structure.


def extrude_walls(obj, wall_height):
    try:
        time_start = time.perf_counter()

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, wall_height)}
        )

        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.object.mode_set(mode="OBJECT")
        cleanup_vertices(obj)

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Extrude walls completed in {duration:.3f} seconds.")
        print()

    except Exception as e:
        print(f"Error in extrude_walls: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                     DEFINE: apply_solidify_modifier                         #
# ----------------------------------------------------------------------------#
#   Applies a solidify modifier to the maze object if enabled,
#   enhancing the wall thickness.


def apply_solidify_modifier(obj, apply_solidify, wall_thickness):

    try:
        if apply_solidify:

            start_time = time.perf_counter()

            solidify_modifier = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
            solidify_modifier.thickness = wall_thickness
            solidify_modifier.solidify_mode = "NON_MANIFOLD"
            solidify_modifier.offset = 0
            bpy.ops.object.modifier_apply(modifier="Solidify")

            end_time = time.perf_counter()
            duration = end_time - start_time
            print()
            print(f"Solidify modifier applied in {duration:.3f} seconds.")
            print()

    except Exception as e:
        print(f"Error in apply_solidify_modifier: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                       DEFINE: apply_bevel modifier                          #
# ----------------------------------------------------------------------------#
#   Applies a bevel modifier to the maze object if enabled, smoothing
#   the edges of the maze walls.


def apply_bevel_modifier(obj, apply_bevel):

    try:
        if apply_bevel:
            start_time = time.perf_counter()

            bevel_modifier = obj.modifiers.new(name="Bevel", type="BEVEL")
            bevel_modifier.width = 0.02
            bevel_modifier.segments = 4
            bpy.ops.object.modifier_apply(modifier="Bevel")

            end_time = time.perf_counter()
            duration = end_time - start_time
            print()
            print(f"Bevel modifier applied in {duration:.3f} seconds.")
            print()

    except Exception as e:
        print(f"Error in apply_bevel_modifier: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                   DEFINE: cleanup_vertices                                  #
# ----------------------------------------------------------------------------#
#    Cleans up non-manifold vertices from the maze mesh
#    to ensure mesh integrity, particularly by removing
#    leftover vertices that do not form part of the maze walls.

#    During the maze generation process, especially after
#    extruding the maze walls, some vertices may remain
#    that are not connected to any significant edges or faces.
#    These vertices can form non-functional edges when
#    which do not contribute to the maze structure and may
#    interfere with both the visual and functional aspects
#    of the maze. This function identifies and removes
#    such vertices to maintain a clean and usable mesh.

#    Process:
#        1. Switches the object to 'EDIT' mode to allow
#           direct manipulation of the mesh.
#        2. Utilizes Blender's bmesh module to access
#           and modify the mesh data directly.
#        3. Identifies non-manifold vertices using
#           Blender's selection tools.
#        4. Removes these vertices to prevent the
#           formation of unwanted edges and to
#           ensure a manifold geometry.
#        4. Removes these vertices to prevent the
#           formation of unwanted edges and to
#           ensure a manifold geometry.
#        5. Returns the object to 'OBJECT' mode
#           after cleaning is complete.

#    Note:
#        This function modifies the mesh data
#        directly and should be used with caution.
#        Ensure that the object is not involved in any
#        other operations during this process to avoid
#        conflicts.


def cleanup_vertices(obj):

    try:
        start_time = time.perf_counter()

        # Switch to edit mode
        bpy.ops.object.mode_set(mode="EDIT")

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # Deselect all elements first
        bpy.ops.mesh.select_all(action="DESELECT")

        isolated_edges = [
            edge
            for edge in bm.edges
            if len(edge.verts[0].link_edges) == 1 and len(edge.verts[1].link_edges) == 1
        ]

        for edge in isolated_edges:
            edge.select = True
        bpy.ops.mesh.delete(type="EDGE")
        bmesh.update_edit_mesh(mesh)

        bpy.ops.object.mode_set(mode="OBJECT")

        end_time = time.perf_counter()
        duration = end_time - start_time
        print()
        print(f"Non-manifold vertices removed in {duration:.3f} seconds. ")
        print()

    except Exception as e:
        print(f"Error in cleanup_vertices: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                        DEFINE: delete_more_walls                            #
# ----------------------------------------------------------------------------#
#    Allows the user to remove small isolated sections (islands) of the maze
#    based on the specified face count threshold.

#    It is useful for simplifying the maze or ensuring that all parts of
#    the maze are accessible by removing smaller, disconnected sections.
#    This operation is optional and can be enabled or disabled based on
#    user preference.

#    Parameters:
#        obj (bpy.types.Object): The Blender object representing the maze
#                                where islands are to be removed.
#        delete_islands (bool): A flag to determine whether island deletion
#                               should be performed. If False, the function
#                               will exit without making changes.
#        island_wall_count (int): The maximum number of walls (faces)
#        an island can have before it is considered for deletion.
#        Only islands with this number of faces or fewer will be deleted.

#    Note:
#        This function operates in 'EDIT' mode to directly manipulate the
#        mesh data of the provided object. It assumes that the object's mesh
#        is well-formed and that the 'obj' parameter correctly references
#        a Blender object with mesh data.


def delete_more_walls(obj, delete_islands, wall_count):

    try:
        time_start = time.perf_counter()

        if delete_islands:
            # Switch to edit mode
            bpy.ops.object.mode_set(mode="EDIT")

            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table()

            # Deselect all elements first
            bpy.ops.mesh.select_all(action="DESELECT")

            # Get all islands (disconnected mesh elements)
            bm.verts.ensure_lookup_table()
            islands = []
            visited = set()

            for vert in bm.verts:

                if vert not in visited:
                    stack = [vert]
                    island = set()

                    while stack:
                        v = stack.pop()

                        if v not in visited:
                            visited.add(v)
                            island.add(v)

                            for edge in v.link_edges:

                                for v2 in edge.verts:

                                    if v2 not in visited:
                                        stack.append(v2)

                    islands.append(island)

            for island in islands:
                faces = [
                    face
                    for face in bm.faces
                    if all(vert in island for vert in face.verts)
                ]

                if len(faces) <= wall_count:
                    for face in faces:
                        face.select = True

            bmesh.update_edit_mesh(mesh)

            bpy.ops.mesh.delete(type="FACE")
            bpy.ops.object.mode_set(mode="OBJECT")

            time_end = time.perf_counter()
            duration = time_end - time_start
            print()
            print(f"Walls with {wall_count} faces removed in {duration:.3f} seconds.")
            print()

    except Exception as e:
        print(f"Error in delete_more_walls: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                    DEFINE: apply_transform_and_cleanup                      #
# ----------------------------------------------------------------------------#
#   Applies transformations to the maze object and sets its origin
#   for consistent scaling and manipulation.


def apply_transform_and_cleanup(obj, wall_height):

    try:
        time_start = time.perf_counter()

        bpy.ops.object.transform_apply(location=True)

        bpy.ops.object.origin_set(type="GEOMETRY_ORIGIN", center="MEDIAN")

        obj.location.z = wall_height / 2
        bpy.ops.object.transform_apply(location=True)

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Transform and cleanup completed in {duration:.3f} seconds.")
        print()

    except Exception as e:
        print(f"Error in apply_transform_and_cleanup: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                          DEFINE: get_world_bounds                           #
# ----------------------------------------------------------------------------#
#   Returns the world-space bounding box of an object's mesh as
#   (x_min, x_max, y_min, y_max, z_min, z_max).

#   We read the actual mesh vertices (rather than the parameter grid size)
#   so the environment objects line up with where the maze really ends up.
#   The maze is recentred on its geometry median during cleanup, and island
#   deletion can shift that, so deriving bounds from the finished mesh is the
#   only reliable way to keep the floor / ceiling / boundary aligned.


def get_world_bounds(obj):

    matrix = obj.matrix_world
    coords = [matrix @ vert.co for vert in obj.data.vertices]

    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]

    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


# ----------------------------------------------------------------------------#
#                           DEFINE: create_plane                              #
# ----------------------------------------------------------------------------#
#   Creates a single flat quad (floor or ceiling) as its own object at the
#   given Z height, spanning the supplied XY extents. When face_down is True
#   the winding is reversed so the normal points downward (for a ceiling).


def create_plane(name, x_min, x_max, y_min, y_max, z, collection, face_down=False):

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    bm = bmesh.new()
    v0 = bm.verts.new((x_min, y_min, z))
    v1 = bm.verts.new((x_max, y_min, z))
    v2 = bm.verts.new((x_max, y_max, z))
    v3 = bm.verts.new((x_min, y_max, z))

    if face_down:
        bm.faces.new((v0, v3, v2, v1))
    else:
        bm.faces.new((v0, v1, v2, v3))

    bm.to_mesh(mesh)
    bm.free()
    return obj


# ----------------------------------------------------------------------------#
#                          DEFINE: _subtract_gaps                             #
# ----------------------------------------------------------------------------#
#   Pure helper. Given a 1D interval [lo, hi] and a list of (gap_lo, gap_hi)
#   gaps, returns the remaining sub-intervals after removing the gaps. Used to
#   carve door openings out of a wall. Handles any number of gaps, including
#   two doors cut into the same wall.


def _subtract_gaps(lo, hi, gaps):

    intervals = [(lo, hi)]

    for gap_lo, gap_hi in sorted(gaps):
        remaining = []
        for a, b in intervals:
            if gap_hi <= a or gap_lo >= b:
                remaining.append((a, b))  # gap does not touch this interval
            else:
                if a < gap_lo:
                    remaining.append((a, gap_lo))
                if gap_hi < b:
                    remaining.append((gap_hi, b))
        intervals = remaining

    return intervals


# ----------------------------------------------------------------------------#
#                      DEFINE: compute_boundary_segments                      #
# ----------------------------------------------------------------------------#
#   Pure geometry helper (no Blender dependency, so it is unit-testable).
#   Returns the list of floor-level wall segments for the boundary frame as
#   ((x1, y1), (x2, y2)) pairs.

#   doors is a list of (side, position, width) openings, where:
#       side     - one of "NORTH", "SOUTH", "EAST", "WEST"
#       position - 0.0..1.0 along that wall (0 = one corner, 0.5 = centre,
#                  1 = the other corner)
#       width    - opening width in world units
#   The width is clamped so an opening can never span an entire side. An empty
#   doors list produces a fully closed rectangle.


def compute_boundary_segments(x_min, x_max, y_min, y_max, thickness, doors):

    #   Each wall is a 1D interval along one axis at a fixed perpendicular
    #   coordinate. We collect door openings per wall, then subtract them.
    walls = {
        "SOUTH": {"fixed": y_min, "lo": x_min, "hi": x_max, "axis": "x"},
        "NORTH": {"fixed": y_max, "lo": x_min, "hi": x_max, "axis": "x"},
        "WEST": {"fixed": x_min, "lo": y_min, "hi": y_max, "axis": "y"},
        "EAST": {"fixed": x_max, "lo": y_min, "hi": y_max, "axis": "y"},
    }

    gaps = {side: [] for side in walls}

    for side, position, width in doors:
        wall = walls.get(side)
        if wall is None:
            continue

        span = wall["hi"] - wall["lo"]
        width = max(0.0, min(width, span - thickness))
        if width <= 0.0:
            continue

        position = max(0.0, min(position, 1.0))
        gap_lo = wall["lo"] + position * (span - width)
        gaps[side].append((gap_lo, gap_lo + width))

    segments = []
    for side, wall in walls.items():
        for lo, hi in _subtract_gaps(wall["lo"], wall["hi"], gaps[side]):
            if hi - lo <= 1e-9:
                continue  # opening consumed the whole sub-interval
            if wall["axis"] == "x":
                segments.append(((lo, wall["fixed"]), (hi, wall["fixed"])))
            else:
                segments.append(((wall["fixed"], lo), (wall["fixed"], hi)))

    return segments


# ----------------------------------------------------------------------------#
#                          DEFINE: create_boundary                            #
# ----------------------------------------------------------------------------#
#   Builds the outer wall frame as its own object: vertical wall segments
#   forming a rectangle around the maze, with entrance/exit openings carved
#   out per the supplied doors list (see compute_boundary_segments).

#   Thickness is provided by a *live* solidify modifier so the user can still
#   adjust the boundary wall thickness after generation.


def create_boundary(
    name, x_min, x_max, y_min, y_max, z_bottom, z_top, thickness, doors, collection
):

    segments = compute_boundary_segments(
        x_min, x_max, y_min, y_max, thickness, doors
    )

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    bm = bmesh.new()
    for (p1, p2) in segments:
        v0 = bm.verts.new((p1[0], p1[1], z_bottom))
        v1 = bm.verts.new((p2[0], p2[1], z_bottom))
        v2 = bm.verts.new((p2[0], p2[1], z_top))
        v3 = bm.verts.new((p1[0], p1[1], z_top))
        bm.faces.new((v0, v1, v2, v3))

    bm.to_mesh(mesh)
    bm.free()

    solidify = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
    solidify.thickness = thickness
    solidify.offset = 0
    return obj


# ----------------------------------------------------------------------------#
#                          DEFINE: _maze_collection                          #
# ----------------------------------------------------------------------------#
#   Returns the collection the maze lives in, so environment objects are
#   linked alongside it.


def _maze_collection(maze_obj):

    if maze_obj.users_collection:
        return maze_obj.users_collection[0]
    return bpy.context.collection


# ----------------------------------------------------------------------------#
#                            DEFINE: _maze_extents                           #
# ----------------------------------------------------------------------------#
#   Returns the environment footprint (x_min, x_max, y_min, y_max, z_min,
#   z_max) around the finished maze. The XY footprint is pushed out by the
#   boundary offset when a boundary is present, otherwise by a small half-cell
#   margin. Z is the maze's own vertical extent.


def _maze_extents(maze_obj, cell_size, boundary_offset, add_boundary):

    x_min, x_max, y_min, y_max, z_min, z_max = get_world_bounds(maze_obj)

    pad = boundary_offset * cell_size if add_boundary else cell_size * 0.5

    return (x_min - pad, x_max + pad, y_min - pad, y_max + pad, z_min, z_max)


# ----------------------------------------------------------------------------#
#                         DEFINE: _doors_from_params                         #
# ----------------------------------------------------------------------------#
#   Builds the (side, position, width) door list from the maze settings.
#   Returns an empty list when entrance/exit cutting is disabled. Pure logic
#   (reads attributes only), so it is unit-testable.


def _doors_from_params(params):

    if not params.add_doors:
        return []

    door_world_width = params.door_width * params.cell_size
    return [
        (params.entrance_side, params.entrance_position, door_world_width),
        (params.exit_side, params.exit_position, door_world_width),
    ]


# ----------------------------------------------------------------------------#
#                        DEFINE: build_environment                            #
# ----------------------------------------------------------------------------#
#   Orchestrates the optional floor / ceiling / boundary objects around the
#   finished maze. Each enabled part is created as its own named object so it
#   can be textured or deleted independently.

#   The footprint matches the boundary extent when a boundary is present, so
#   the floor and ceiling reach all the way out under the frame; otherwise it
#   is the maze extent plus a small half-cell margin.


def build_environment(
    maze_obj,
    cell_size,
    wall_thickness,
    add_floor,
    add_ceiling,
    add_boundary,
    boundary_offset,
    doors,
):

    try:
        time_start = time.perf_counter()

        collection = _maze_collection(maze_obj)
        x_min, x_max, y_min, y_max, z_min, z_max = _maze_extents(
            maze_obj, cell_size, boundary_offset, add_boundary
        )

        if add_floor:
            create_plane(
                "Maze_Floor", x_min, x_max, y_min, y_max, z_min, collection
            )

        if add_ceiling:
            create_plane(
                "Maze_Ceiling", x_min, x_max, y_min, y_max, z_max,
                collection, face_down=True,
            )

        if add_boundary:
            create_boundary(
                "Maze_Boundary", x_min, x_max, y_min, y_max,
                z_min, z_max, wall_thickness, doors, collection,
            )

        time_end = time.perf_counter()
        duration = time_end - time_start
        print()
        print(f"Environment built in {duration:.3f} seconds.")
        print()

    except Exception as e:
        print(f"Error in build_environment: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                         DEFINE: rebuild_boundary                           #
# ----------------------------------------------------------------------------#
#   Rebuilds only the Maze_Boundary object, leaving the maze, floor and
#   ceiling untouched. Moving a door only affects the boundary, so there is no
#   need to regenerate the whole maze -- this keeps "Randomise Exit" instant
#   even on large mazes.

#   Returns True if a maze was present (boundary rebuilt or cleared), or False
#   if there is no maze to work from.


def rebuild_boundary(params):

    maze_obj = bpy.data.objects.get("Maze")
    if maze_obj is None:
        return False

    existing = bpy.data.objects.get("Maze_Boundary")
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    if params.add_boundary:
        collection = _maze_collection(maze_obj)
        x_min, x_max, y_min, y_max, z_min, z_max = _maze_extents(
            maze_obj, params.cell_size, params.boundary_offset, True
        )
        create_boundary(
            "Maze_Boundary", x_min, x_max, y_min, y_max,
            z_min, z_max, params.wall_thickness, _doors_from_params(params), collection,
        )

    return True


# ----------------------------------------------------------------------------#
#                        DEFINE: _deselect_all_objects                        #
# ----------------------------------------------------------------------------#
#   Deselects every object in the current view layer so maze generation starts
#   from a clean state and does not disturb unrelated objects.


def _deselect_all_objects():

    try:
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)

    except Exception as e:
        print(f"Error in _deselect_all_objects: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                        DEFINE: _delete_existing_maze                        #
# ----------------------------------------------------------------------------#
#   Removes the maze and any environment objects from a previous run so
#   regenerating does not accumulate duplicates. Suffixed copies (e.g.
#   "Maze.001") are intentionally left alone.


def _delete_existing_maze():

    try:
        for name in ("Maze", "Maze_Floor", "Maze_Ceiling", "Maze_Boundary"):
            existing = bpy.data.objects.get(name)
            if existing:
                bpy.data.objects.remove(existing, do_unlink=True)

    except Exception as e:
        print(f"Error in _delete_existing_maze: {str(e)}")
        raise


# ----------------------------------------------------------------------------#
#                           DEFINE: run_generation                           #
# ----------------------------------------------------------------------------#
#   The full maze generation pipeline, factored out so multiple operators can
#   share it. `params` is any object exposing the maze settings as attributes
#   -- both the GenerateMaze operator (self) and the stored operator
#   properties from operator_properties_last() satisfy this.

#   Calling this directly (rather than re-invoking the operator via bpy.ops)
#   means changes apply immediately, which is what lets "Randomise Exit"
#   regenerate in a single click.


def run_generation(params):

    random.seed(params.random_seed)

    _deselect_all_objects()
    _delete_existing_maze()

    create_grid(
        params.rows,
        params.columns,
        params.cell_size,
        params.wall_height,
        params.iterations,
        params.delete_islands,
        params.wall_count,
        params.apply_solidify,
        params.wall_thickness,
        params.apply_bevel,
    )

    #   Build the optional environment (floor / ceiling / boundary) around the
    #   finished maze. Only runs when at least one option is enabled, so the
    #   default output is unchanged.
    maze_obj = bpy.data.objects.get("Maze")
    if maze_obj is not None and (
        params.add_floor or params.add_ceiling or params.add_boundary
    ):
        build_environment(
            maze_obj,
            params.cell_size,
            params.wall_thickness,
            params.add_floor,
            params.add_ceiling,
            params.add_boundary,
            params.boundary_offset,
            _doors_from_params(params),
        )


# ----------------------------------------------------------------------------#
#                           DEFINE: opposite_side                            #
# ----------------------------------------------------------------------------#
#   Returns the wall opposite the given side (e.g. NORTH -> SOUTH). Unknown
#   values are returned unchanged. Pure helper, so it is unit-testable.


def opposite_side(side):

    return _OPPOSITE_SIDE.get(side, side)


# ----------------------------------------------------------------------------#
#                       CLASS: OBJECT_OT_RandomiseDoor                        #
# ----------------------------------------------------------------------------#
#   Operator behind the "Randomise Entrance" and "Randomise Exit" buttons. It
#   moves the chosen door (set via the `target` property) to the wall opposite
#   the *other* door, picks a random position along that wall, and rebuilds
#   only the boundary. The maze, floor and ceiling are untouched, so it stays
#   instant and can be pressed repeatedly to shuffle one door.


class OBJECT_OT_RandomiseDoor(bpy.types.Operator):
    bl_idname = "object.randomise_maze_door"
    bl_label = "Randomise Door"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Target",
        items=[
            ("ENTRANCE", "Entrance", "Randomise the entrance"),
            ("EXIT", "Exit", "Randomise the exit"),
        ],
        default="EXIT",
        options={"HIDDEN"},
    )

    @classmethod
    def description(cls, context, properties):
        other = "exit" if properties.target == "ENTRANCE" else "entrance"
        target = properties.target.lower()
        return (
            f"Move the {target} to the wall opposite the {other}, at a random "
            "position"
        )

    def execute(self, context):

        props = context.window_manager.operator_properties_last(OGM)
        if props is None:
            self.report({"WARNING"}, "Generate a maze first, then randomise.")
            return {"CANCELLED"}

        if not (props.add_boundary and props.add_doors):
            self.report(
                {"WARNING"}, "Enable Add Boundary Walls and Cut Entrance/Exit first."
            )
            return {"CANCELLED"}

        try:
            #   Use an independent RNG seeded from system entropy. The global
            #   random module is reseeded during maze generation, so drawing
            #   from it here would yield the same result on every click -- this
            #   keeps repeated presses genuinely random.
            #
            #   Each door is placed on the wall opposite the *other* door.
            if self.target == "ENTRANCE":
                props.entrance_side = opposite_side(props.exit_side)
                props.entrance_position = random.Random().random()
                moved_side, moved_position = props.entrance_side, props.entrance_position
            else:
                props.exit_side = opposite_side(props.entrance_side)
                props.exit_position = random.Random().random()
                moved_side, moved_position = props.exit_side, props.exit_position

            #   Only the boundary depends on door positions, so rebuild just
            #   that object. The maze, floor and ceiling are left untouched,
            #   which keeps this instant even on large mazes.
            if not rebuild_boundary(props):
                self.report({"WARNING"}, "Generate a maze first, then randomise.")
                return {"CANCELLED"}

            self.report(
                {"INFO"},
                f"{self.target.title()} moved to {moved_side.title()} "
                f"at {moved_position:.2f}",
            )

        except Exception as e:
            self.report({"ERROR"}, f"Failed to randomise {self.target.lower()}: {str(e)}")
            return {"CANCELLED"}

        return {"FINISHED"}


# ----------------------------------------------------------------------------#
#                        CLASS: VIEW3D_PT_CreateMazeMenu                      #
# ----------------------------------------------------------------------------#
#   UI panel for the 3D Viewport that provides a user interface
#   to control maze generation parameters.


class VIEW3D_PT_CreateMazeMenu(bpy.types.Panel):
    bl_label = "Maze Generator"
    bl_idname = "VIEW3D_PT_CreateMazeMenu"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Create"
    bl_description = "Generate a maze with customizable parameters"

    # ------------------------------------------------------------------------#
    #                                DEFINE: draw                             #
    # ------------------------------------------------------------------------#
    #   Draws the UI elements for controlling maze
    #   generation within the 3D Viewport's Create menu.

    #   This method populates the panel with interactive
    #   controls that allow users to:
    #       - Initiate maze generation via a button.
    #       - Adjust key maze parameters such as size,
    #         complexity, and modifiers in real-time.
    #       - Each control is linked to a property that
    #         influences the maze generation algorithm when
    #         the 'Generate Maze' button is pressed.

    #   The layout is organized to provide a user-friendly interface,
    #   with parameters grouped logically to guide the user
    #   through the setup process.

    def draw(self, context):
        layout = self.layout

        #   Generate a variable to shorten the code here

        wm = context.window_manager

        layout.operator(OGM, text="Generate Maze", icon="CUBE")

        #   Fetch the last-used operator properties once. On a fresh Blender
        #   start (before the operator has ever run) this can be None, so we
        #   guard against it to avoid a draw-time error in the panel.
        props = wm.operator_properties_last(OGM)
        if props is None:
            return

        layout.prop(props, "random_seed")
        layout.prop(props, "rows")
        layout.prop(props, "columns")
        layout.prop(props, "cell_size")
        layout.prop(props, "wall_height")
        layout.prop(props, "iterations")

        layout.separator()

        layout.prop(props, "delete_islands")
        layout.prop(props, "wall_count")

        layout.separator()

        layout.prop(props, "apply_solidify")
        layout.prop(props, "wall_thickness")
        layout.prop(props, "apply_bevel")

        layout.separator()

        layout.prop(props, "add_floor")
        layout.prop(props, "add_ceiling")
        layout.prop(props, "add_boundary")
        layout.prop(props, "boundary_offset")
        layout.prop(props, "add_doors")
        layout.prop(props, "door_width")
        layout.prop(props, "entrance_side")
        layout.prop(props, "entrance_position")
        layout.prop(props, "exit_side")
        layout.prop(props, "exit_position")

        randomise_row = layout.row(align=True)
        randomise_row.operator(
            "object.randomise_maze_door", text="Randomise Entrance", icon="FILE_REFRESH"
        ).target = "ENTRANCE"
        randomise_row.operator(
            "object.randomise_maze_door", text="Randomise Exit", icon="FILE_REFRESH"
        ).target = "EXIT"


classes = (
    OBJECT_OT_GenerateMaze,
    OBJECT_OT_RandomiseDoor,
    VIEW3D_PT_CreateMazeMenu,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
