import time, json, copy

from visualizer import *
from stadium_variables import *
import calc_batting
import PySimpleGUI as sg
from random import randint

render_dimensions = (1280, 720)

KEYBOARD_CAMERA_CONTROLS = {
    pygame.K_w      : lambda movement, delta_time, sensitivity : movement + (Vector3(0, 0, 1) * delta_time * sensitivity),
    pygame.K_s      : lambda movement, delta_time, sensitivity : movement - (Vector3(0, 0, 1) * delta_time * sensitivity),
    pygame.K_q      : lambda movement, delta_time, sensitivity : movement + (Vector3(0, 1, 0) * delta_time * sensitivity),
    pygame.K_e      : lambda movement, delta_time, sensitivity : movement - (Vector3(0, 1, 0) * delta_time * sensitivity),
    pygame.K_a      : lambda movement, delta_time, sensitivity : movement + (Vector3(1, 0, 0) * delta_time * sensitivity),
    pygame.K_d      : lambda movement, delta_time, sensitivity : movement - (Vector3(1, 0, 0) * delta_time * sensitivity),
    pygame.K_LSHIFT : lambda movement, delta_time, sensitivity : movement * 2.0,
}

class RenderedBattingScene:
    def __init__(self) -> None:
        self.screen = canvas(render_dimensions)
        self.stadium:MssbStadium = None
        self.stadium_graphics_list = None
        self.camera_sensitivity = 10.0

        self.proj_mat = self.screen.make_projection_horizontal(80.0, render_dimensions[0]/render_dimensions[1], 0.1, 200.0)

        self.view_pos = Vector3(0, 2, -5)
        self.view_rot = Vector3()

        self.frame_counter = 0
        self.start_time = self.old_time = self.get_time()
        self.batting_json = {}

        self.saved_final_spots = None
    
    def set_batting_json(self, d:dict):
        if d != self.batting_json:
            self.batting_json = d

            if self.saved_final_spots != None:
                self.screen.delete_list(self.saved_final_spots)
                self.saved_final_spots = None
    

    def get_time(self):
        return time.perf_counter_ns() * 1e-9

    def get_new_view(self)->mat:
        # m = mat([[]])
        # m.set_size(4, 4)
        # # m.v[3][2] = 5.0
        # return m 
        scale_flip = scale_mat(Vector3(-1.0, 1.0, -1.0))
        scale_render = scale_mat(Vector3(1.0, -1.0, 1.0))

        r_mat = rotation_mat(self.view_rot)
        t_mat = translation_mat(self.view_pos)
        new_view = r_mat * scale_render * t_mat * scale_flip
        return new_view

    def update_variables(self):

        new_time = self.get_time()
        dt = new_time - self.old_time
        self.old_time = new_time
        self.frame_counter = int((new_time - self.start_time) * 60)
        self.screen.update_events()

        # camera movement
        movement = Vector3()

        for key, func in KEYBOARD_CAMERA_CONTROLS.items():
            if self.screen.is_pressed(key):
                movement = func(movement, dt, self.camera_sensitivity)

        # update render position if we moved
        if movement.length() > 0:
            i = self.get_new_view()
            # movement *= -1
            t = translation_mat(movement)
            
            new_mat = t * i
            new_mat:mat

            output_loc = new_mat.inv() * vec3_to_vec4(Vector3(0.0, 0.0, 0.0))

            self.view_pos = output_loc.xyz
            self.view_pos.y *= -1

        # update the rotation matrix if right click is held
        if self.screen.is_right_button_down():
            new_move = self.screen.mouse_move
            self.view_rot = Vector3(self.view_rot.x + new_move.y, self.view_rot.y - new_move.x, self.view_rot.z)
    
    def render(self):
        self.screen.clear((0, 0, 0))

        self.screen.set_matrices(self.get_new_view(), self.proj_mat)

        self.draw_stadium()

        self.draw_ball_path()

        self.draw_bat()

        self.draw_batter()

        self.screen.present()

    def draw_batter(self):
        try:
            batter_x = self.batting_json.get("batter_x", 0)
            handedness = self.batting_json.get("handedness", 0)
            batter_id = self.batting_json.get("batter_id", 0)

            hbox_batter = calc_batting.get_hitbox(batter_id)
                
            batter_width = hbox_batter[0] / 100
            batter_hitbox_near =  hbox_batter[1] / 100
            batter_hitbox_far =  hbox_batter[2] / -100

            batter_offset_x = calc_batting.BATTER_HITBOXES[batter_id]["EasyBattingSpotHorizontal"]
            batter_offset_z = calc_batting.BATTER_HITBOXES[batter_id]["EasyBattingSpotVertical"]

            if handedness == 1:
                batter_x *= -1
                batter_offset_x *= -1
                batter_hitbox_near *= -1
                batter_hitbox_far *= -1
            
            height = 2
            slight_offset = 0.001

            for p in [batter_hitbox_near, batter_hitbox_far]:
                self.screen.draw_cube(position=Vector3(batter_x + batter_offset_x, slight_offset, batter_offset_z), scale=Vector3(p, height, batter_width), offset=Vector3(p/2, height/2, batter_width/2), filled=False, color=(0, 255, 255))
            
            self.screen.draw_text(Vector3(batter_x + batter_offset_x, slight_offset, batter_offset_z - slight_offset), Vector3(1, 0, 0), text=calc_batting.get_name(batter_id), text_size=24, rendered_height=0.25)

        except:
            pass

    def draw_bat(self):
        try:
            batter_x = self.batting_json.get("batter_x", 0)
            handedness = self.batting_json.get("handedness", 0)
            batter_id = self.batting_json.get("batter_id", 0)

            if handedness == 1:
                batter_x *= -1

            near_far = calc_batting.get_bat_hitbox(batter_id, 0, handedness)
            
            for p in near_far:
                self.screen.draw_cube(position=Vector3(batter_x, 1, 0), scale=Vector3(p, 0.1, 0.1), offset=Vector3((p/2), 0, 0))

        except:
            pass

    def draw_ball_path(self):
        try:
            count = 1 if "override_vertical_range" in self.batting_json else 5

            for i in range(count):
                kwargs = copy.deepcopy(self.batting_json)
                if self.batting_json.get("show_one_hit", False) != True:
                    kwargs.setdefault("override_vertical_range", i) 
                kwargs.setdefault("rand_1", 1565)
                kwargs.setdefault("rand_2", 20008)
                kwargs.setdefault("rand_3", 1628)

                res = calc_batting.hit_ball(**kwargs)["FlightDetails"]["Path"]
                if len(res) > 0:
                    new_points = [
                        dict_to_vec3(x)
                        for x 
                        in res
                    ]
                    self.screen.draw_lines(new_points, line_width=5)
                    self.screen.draw_text(new_points[-1], Vector3(1, 0, 0), str(new_points[-1]), text_size=24, rendered_height=0.5)

                    self.screen.draw_sphere(new_points[self.frame_counter % len(new_points)], radius=0.1, resolution=5)

            if isinstance(self.batting_json["generate_random_hits"], int) and self.batting_json["generate_random_hits"] > 0 and self.saved_final_spots == None:
                self.saved_final_spots = self.screen.start_new_list()

                for i in range(self.batting_json["generate_random_hits"]):
                    kwargs = copy.deepcopy(self.batting_json)
                    kwargs.setdefault("rand_1", randint(0, (2**15)-1))
                    kwargs.setdefault("rand_2", randint(0, (2**15)-1))
                    kwargs.setdefault("rand_3", randint(0, (2**15)-1))

                    final_spot = calc_batting.hit_ball(**kwargs)["FlightDetails"]["Path"][-1]
                    final_spot = dict_to_vec3(final_spot)
                    self.screen.draw_sphere(final_spot, radius=0.1, resolution=2)

                self.screen.end_list(self.saved_final_spots)

            if self.saved_final_spots != None:
                self.screen.call_list(self.saved_final_spots)

        except:
            if self.saved_final_spots != None:
                self.screen.delete_list(self.saved_final_spots)
                self.saved_final_spots = None
            pass

    def set_stadium(self, stadium:MssbStadium):
        self.stadium = stadium
        self.record_stadium()

    def draw_stadium(self):
        if self.stadium_graphics_list != None:
            self.screen.call_list(self.stadium_graphics_list)

    def record_stadium(self):
        if self.stadium == None:
            return

        if self.stadium_graphics_list != None: 
            self.screen.delete_list(self.stadium_graphics_list)

        self.stadium_graphics_list = self.screen.start_new_list()

        stadium_flip = Vector3(1, -1, 1)

        for vertCollection in self.stadium.vertex_collection:
            for tris in vertCollection.triangle_collection:
                points = [
                    p.point.elementwise() * stadium_flip.elementwise()
                    for p
                    in tris.points
                ]
                
                if tris.collection_type == STADIUM_TRIANGLE_COLLECTION_SINGLES:
                    r = range(0, len(points), 3)
                    triangle_method = self.screen.draw_triangles

                elif tris.collection_type == STADIUM_TRIANGLE_COLLECTION_STRIP:
                    r = range(0, len(points)-2)
                    triangle_method = self.screen.draw_triangle_strip


                for i in r:
                    # get just the vec3s
                    new_points = points[i:i+3]
                    # third point in the triangle defines the collision type
                    color = tri_type_to_color(tris.points[i+2].stadium_type)

                    triangle_method(new_points, filled=True, color=color, draw_normals=False)
                    triangle_method(new_points, filled=False, color=contrast_color(color), draw_normals=False)

        self.screen.end_list(self.stadium_graphics_list)


class ParameterWindow:
    def __init__(self) -> None:
        layout = [
            [sg.Multiline("{}", key="-BATTING-JSON-", enable_events=True, expand_y=True, auto_size_text=True)],
            [sg.Button("Instructions", key="-INSTRUCTIONS-", enable_events=True), sg.Button("Show Resulting Hit Details", key="-SHOW-HIT-DETAILS-", enable_events=True)],
        ]

        self.window = sg.Window("Render Parameters", layout, resizable=True, enable_close_attempted_event=True)
        self.parsed_input = {}
        self.instructions_text = ""

    def update_values(self):
        new_input = None
        json_updated = False
        for event_values in self.window.read(timeout=1/1000):
            if event_values == None or event_values == "__TIMEOUT__":
                break

            event = event_values
            if event == "-WINDOW CLOSE ATTEMPTED-":
                exit()
            elif event == "-BATTING-JSON-":
                json_updated = True
                try:
                    new_input = json.loads(self.window["-BATTING-JSON-"].get())
                except:
                    new_input = None
            elif event == "-INSTRUCTIONS-":
                layout = [[sg.Text(self.instructions_text, key='TEXT')]]
                sg.Window(f'Instructions', layout, finalize=True)
            elif event == "-SHOW-HIT-DETAILS-":
                try:
                    res_json = calc_batting.hit_ball(**self.parsed_input)
                    if "FlightDetails" in res_json and "Path" in res_json["FlightDetails"]:
                        res_json["FlightDetails"].pop("Path")
                    layout = [[sg.Multiline(json.dumps(res_json, indent=2), key="-BATTING-JSON-", expand_y=True, auto_size_text=True)]]
                    sg.Window(f'Hit Details', layout, finalize=True, resizable=True)
                except Exception as e:
                    pass

        if json_updated:
            self.parsed_input = new_input

        return json_updated

def main():
    renderer = RenderedBattingScene()
    param_window = ParameterWindow()

    with open("instructions.txt", "r") as f:
        param_window.instructions_text = f.read()

    with open("Mario stadium.json", "r") as f:
        renderer.set_stadium(read_stadium(json.load(f)))

    while True:
        json_update = param_window.update_values()
        if json_update:
            renderer.set_batting_json(param_window.parsed_input)
        renderer.update_variables()
        renderer.render()

if __name__ == "__main__":
    main()