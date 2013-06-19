"""Rayleigh-Taylor instability problem"""

# PyZoltan imports
from pyzoltan.core.carray import LongArray

# PySPH imports
from pysph.base.utils import get_particle_array
from pysph.base.kernels import Gaussian, WendlandQuintic, CubicSpline
from pysph.solver.solver import Solver
from pysph.solver.application import Application
from pysph.sph.integrator import TransportVelocityIntegrator

# the eqations
from pysph.sph.equations import Group, BodyForce
from pysph.sph.transport_velocity_equations import TransportVelocitySummationDensity,\
    TransportVelocitySolidWall, TransportVelocityMomentumEquation

# numpy
import numpy as np

# domain and reference values
gy = -1.0
Lx = 1.0; Ly = 2.0
Re = 420; Umax = np.sqrt(2*abs(gy)*Ly)
nu = Umax*Ly/Re

# density for the two phases
rho1 = 1.8; rho2 = 1.0

# speed of sound and reference pressure
c0 = 10 * Umax
p0 = c0**2

# Numerical setup
nx = 50; dx = Lx/nx
ghost_extent = 5 * dx
hdx = 1.2

def create_particles(empty=False, **kwargs):
    if empty:
        fluid = get_particle_array(name='fluid')
        solid = get_particle_array(name='solid')
    else:
        # create all the particles
        _x = np.arange( -ghost_extent - dx/2, Lx + ghost_extent + dx/2, dx )
        _y = np.arange( -ghost_extent - dx/2, Ly + ghost_extent + dx/2, dx )
        x, y = np.meshgrid(_x, _y); x = x.ravel(); y = y.ravel()

        # sort out the fluid and the solid
        indices = []
        for i in range(x.size):
            if ( (x[i] > 0.0) and (x[i] < Lx) ):
                if ( (y[i] > 0.0)  and (y[i] < Ly) ):
                    indices.append(i)

        to_extract = LongArray(len(indices)); to_extract.set_data(np.array(indices))

        # create the arrays
        solid = get_particle_array(name='solid', x=x, y=y)

        # remove the fluid particles from the solid
        fluid = solid.extract_particles(to_extract); fluid.set_name('fluid')
        solid.remove_particles(to_extract)

        # sort out the two fluid phases
        indices = []
        for i in range(fluid.get_number_of_particles()):
            if fluid.y[i] > 1 - 0.15*np.sin(2*np.pi*fluid.x[i]):
                fluid.rho[i] = rho1
            else:
                fluid.rho[i] = rho2
        
        print "Rayleigh Taylor Instability problem :: Re = %d, nfluid = %d, nsolid=%d"%(
            Re, fluid.get_number_of_particles(),
            solid.get_number_of_particles())

    # add requisite properties to the arrays:
    # particle volume
    fluid.add_property( {'name': 'V'} )
    solid.add_property( {'name': 'V'} )
        
    # advection velocities and accelerations
    fluid.add_property( {'name': 'uhat'} )
    fluid.add_property( {'name': 'vhat'} )

    solid.add_property( {'name': 'uhat'} )
    solid.add_property( {'name': 'vhat'} )

    fluid.add_property( {'name': 'auhat'} )
    fluid.add_property( {'name': 'avhat'} )

    fluid.add_property( {'name': 'au'} )
    fluid.add_property( {'name': 'av'} )
    fluid.add_property( {'name': 'aw'} )

    # reference densities and pressures
    fluid.add_property( {'name': 'rho0'} )
    fluid.rho0[:] = fluid.rho[:]

    fluid.add_property( {'name': 'p0'} )
    fluid.p0[:] = c0**2/fluid.rho
    
    # kernel summation correction for the solid
    solid.add_property( {'name': 'wij'} )

    # imopsed velocity on the solid
    solid.add_property( {'name': 'u0'} )
    solid.add_property( {'name': 'v0'} )                         
        
    # setup the particle properties
    if not empty:
        volume = dx * dx

        # mass is set to get the reference density of each phase
        fluid.m[:] = volume * fluid.rho

        # volume is set as dx^2
        fluid.V[:] = 1./volume
        solid.V[:] = 1./volume

        # smoothing lengths
        fluid.h[:] = hdx * dx
        solid.h[:] = hdx * dx
                
    # return the arrays
    return [fluid, solid]

# Create the application.
app = Application()

# Create the kernel
kernel = WendlandQuintic(dim=2)

# Create a solver.
solver = Solver(
    kernel=kernel, dim=2, integrator_type=TransportVelocityIntegrator)

# Setup default parameters.
solver.set_time_step(7.5e-4)
solver.set_final_time(30)

equations = [

    # Summation density for each phase
    Group(
        equations=[
            TransportVelocitySummationDensity(
                dest='fluid', sources=['fluid','solid'], c0=c0),
            ]),
    
    # boundary conditions for the solid wall from each phase
    Group(
        equations=[
            TransportVelocitySolidWall(
                dest='solid', sources=['fluid'], p0=p0, gy=gy),
            ]),
    
    # acceleration equations for each phase
    Group(
        equations=[
            BodyForce(dest='fluid', sources=None, fy=gy),
            TransportVelocityMomentumEquation(
                dest='fluid', sources=['fluid', 'solid'], nu=nu, pb=p0),
            ]),
    ]

# Setup the application and solver.  This also generates the particles.
app.setup(solver=solver, equations=equations, 
          particle_factory=create_particles)

with open('rt.pyx', 'w') as f:
    app.dump_code(f)

app.run()
