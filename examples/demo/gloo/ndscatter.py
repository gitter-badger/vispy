# -*- coding: utf-8 -*-
# vispy: gallery 2000

"""N-dimensional scatter plot with GPU-based projections.
The projection axes evolve smoothly over time, following a path on the
Lie group SO(n).
"""

from vispy import gloo
from vispy import app
from vispy.color import ColorArray
from vispy.io import load_iris
import numpy as np
from scipy.linalg import expm, logm


class OrthogonalPath(object):
    """Implement a continuous path on the Lie group SO(n).

            >>> op = OrthogonalPath(mat1, mat2)
            >>> mat = op(t)

    """
    def __init__(self, mat, origin=None):
        if origin is None:
            origin = np.eye(len(mat))
        self.a, self.b = np.matrix(origin), np.matrix(mat)
        self._logainvb = logm(self.a.I * self.b)

    def __call__(self, t):
        return np.real(self.a * expm(t * self._logainvb))

# Load the Iris dataset and normalize.
iris = load_iris()
position = iris['data'].astype(np.float32)
n, ndim = position.shape
position -= position.mean()
position /= np.abs(position).max()
v_position = position*.75

v_color = ColorArray(['orange', 'magenta', 'darkblue'])
v_color = v_color.rgb[iris['group'], :].astype(np.float32)
v_color *= np.random.uniform(.5, 1.5, (n, 3))
v_color = np.clip(v_color, 0, 1)
v_size = np.random.uniform(2, 12, (n, 1)).astype(np.float32)

VERT_SHADER = """
#version 120
attribute vec4 a_position;
attribute vec3 a_color;
attribute float a_size;

uniform vec2 u_pan;
uniform vec2 u_scale;
uniform vec4 u_vec1;
uniform vec4 u_vec2;

varying vec4 v_fg_color;
varying vec4 v_bg_color;
varying float v_radius;
varying float v_linewidth;
varying float v_antialias;

void main (void) {
    v_radius = a_size;
    v_linewidth = 1.0;
    v_antialias = 1.0;
    v_fg_color  = vec4(0.0,0.0,0.0,0.5);
    v_bg_color  = vec4(a_color,    1.0);
    
    vec2 position = vec2(dot(a_position, u_vec1),
                         dot(a_position, u_vec2));
    
    vec2 position_tr = u_scale * (position + u_pan);
    gl_Position = vec4(position_tr, 0.0, 1.0);
    gl_PointSize = 2.0*(v_radius + v_linewidth + 1.5*v_antialias);
}
"""

FRAG_SHADER = """
#version 120
varying vec4 v_fg_color;
varying vec4 v_bg_color;
varying float v_radius;
varying float v_linewidth;
varying float v_antialias;
void main()
{
    float size = 2.0*(v_radius + v_linewidth + 1.5*v_antialias);
    float t = v_linewidth/2.0-v_antialias;
    float r = length((gl_PointCoord.xy - vec2(0.5,0.5))*size);
    float d = abs(r - v_radius) - t;
    if( d < 0.0 )
        gl_FragColor = v_fg_color;
    else
    {
        float alpha = d/v_antialias;
        alpha = exp(-alpha*alpha);
        if (r > v_radius)
            gl_FragColor = vec4(v_fg_color.rgb, alpha*v_fg_color.a);
        else
            gl_FragColor = mix(v_bg_color, v_fg_color, alpha);
    }
}
"""


class Canvas(app.Canvas):
    def __init__(self):
        app.Canvas.__init__(self, position=(50, 50), keys='interactive')

        self.program = gloo.Program(VERT_SHADER, FRAG_SHADER)

        self.program['a_position'] = gloo.VertexBuffer(v_position)
        self.program['a_color'] = gloo.VertexBuffer(v_color)
        self.program['a_size'] = gloo.VertexBuffer(v_size)
        
        self.program['u_pan'] = (0., 0.)
        self.program['u_scale'] = (1., 1.)
        
        self.program['u_vec1'] = (1., 0., 0., 0.)
        self.program['u_vec2'] = (0., 1., 0., 0.)
            
        # Circulant matrix.
        circ = np.diagflat(np.ones(ndim-1), 1)
        circ[-1, 0] = -1 if ndim % 2 == 0 else 1
        self._op = OrthogonalPath(np.eye(ndim), circ)
        
        self._timer = app.Timer('auto', connect=self.on_timer)

    def on_timer(self, event):
        mat = self._op(event.elapsed)
        self.program['u_vec1'] = mat[:, 0].squeeze()
        self.program['u_vec2'] = mat[:, 1].squeeze()
        self.update()
        
    def on_initialize(self, event):
        gloo.set_state(clear_color=(1, 1, 1, 1), blend=True, 
                       blend_func=('src_alpha', 'one_minus_src_alpha'))
        self._timer.start()

    def on_resize(self, event):
        self.width, self.height = event.size
        gloo.set_viewport(0, 0, self.width, self.height)

    def on_draw(self, event):
        gloo.clear()
        self.program.draw('points')

if __name__ == '__main__':
    c = Canvas()
    c.show()
    app.run()
