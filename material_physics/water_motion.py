"""Approximate six-DOF box dynamics in still water, SI units.

Water motion does not feed back from Mantaflow. Hydrostatics and distributed
drag are integrated here; Mantaflow later responds to the baked box motion.
"""
import math
import numpy as np

def rotation(q):
    w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def qmul(a,b):
    w,x,y,z=a; v,i,j,k=b
    return np.array([w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,
                     w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v])

def simulate(density=600., dimensions=(1.,1.,1.), height=1.8,
             seconds=10., fps=24, substeps=12, water_density=1000.,
             pool_area=36., cells=12, drag_coefficient=1.25):
    dims=np.asarray(dimensions,dtype=float)
    if not 0<density<water_density: raise ValueError('落水漂浮演示需要物体密度大于零且小于水密度')
    volume=float(np.prod(dims)); mass=density*volume
    inertia=mass/12*np.array([dims[1]**2+dims[2]**2,dims[0]**2+dims[2]**2,dims[0]**2+dims[1]**2])
    grid=np.stack(np.meshgrid(*[(np.arange(cells)+.5)/cells-.5]*3,indexing='ij'),axis=-1).reshape(-1,3)*dims
    cell_volume=volume/len(grid)
    q=qmul(qmul(np.array([math.cos(.07),math.sin(.07),0.,0.]),
                np.array([math.cos(-.05),0.,math.sin(-.05),0.])),
                np.array([math.cos(.04),0.,0.,math.sin(.04)]))
    half_height=float(np.abs(rotation(q)[2])@dims/2)
    pos=np.array([0.,0.,height+half_height]); velocity=np.zeros(3); omega=np.zeros(3)
    dt=1/(fps*substeps); records=[]; water_level=0.; first_contact=None; max_submerged=0.
    min_center=pos[2]; max_speed=0.
    def submerged(r, matrix):
        nonlocal water_level
        half=max(float(np.abs(matrix[2])@(dims/cells)/2),1e-6)
        for _ in range(3):
            fraction=np.clip((water_level-(pos[2]+r[:,2])+half)/(2*half),0,1)
            water_level=float(fraction.sum()*cell_volume/pool_area)
        return fraction
    for step in range(round(seconds*fps)*substeps+1):
        matrix=rotation(q); r=grid@matrix.T
        fraction=submerged(r,matrix); wet_volume=float(fraction.sum()*cell_volume)
        if wet_volume>1e-6 and first_contact is None: first_contact=step*dt
        max_submerged=max(max_submerged,wet_volume/volume)
        min_center=min(min_center,float(pos[2])); max_speed=max(max_speed,float(np.linalg.norm(velocity)))
        if step%substeps==0:
            records.append({'frame':step//substeps+1,'time':step*dt,'position':pos.tolist(),
                            'quaternion':q.tolist(),'velocity':velocity.tolist(),
                            'omega':omega.tolist(),'submerged_fraction':wet_volume/volume,
                            'water_level':water_level})
        if step==round(seconds*fps)*substeps: break
        weights=fraction*cell_volume
        force_cells=np.zeros_like(r); force_cells[:,2]=water_density*9.81*weights
        local_v=velocity+np.cross(omega,r)
        speed=np.linalg.norm(local_v,axis=1)
        length=volume**(1/3)
        # Distributed pressure-drag approximation. Low-speed damping controls
        # unresolved viscous/wave losses; neither coefficient is a measurement.
        force_cells-=((.5*water_density*drag_coefficient*speed/length+1000.)*weights)[:,None]*local_v
        force=force_cells.sum(axis=0)+np.array([0.,0.,-mass*9.81])
        torque=np.cross(r,force_cells).sum(axis=0)-omega*(mass*.45*length**2*wet_volume/volume)
        omega_body=matrix.T@omega
        alpha=matrix@((matrix.T@torque-np.cross(omega_body,inertia*omega_body))/inertia)
        velocity+=force/mass*dt; pos+=velocity*dt; omega+=alpha*dt
        angle=float(np.linalg.norm(omega))*dt
        if angle>1e-12:
            dq=np.concatenate(([math.cos(angle/2)],omega/np.linalg.norm(omega)*math.sin(angle/2)))
            q=qmul(dq,q); q/=np.linalg.norm(q)
    metrics={'density_kg_m3':density,'mass_kg':mass,'volume_m3':volume,
             'water_density_kg_m3':water_density,'gravity_m_s2':9.81,
             'drop_clearance_m':height,'first_contact_s':first_contact,
             'max_submerged_fraction':max_submerged,'min_center_z_m':min_center,
             'max_speed_m_s':max_speed,'final_submerged_fraction':records[-1]['submerged_fraction'],
             'expected_equilibrium_fraction':density/water_density,
             'final_speed_m_s':float(np.linalg.norm(velocity)),
             'final_angular_speed_rad_s':float(np.linalg.norm(omega)),
             'method':'Voxel quadrature hydrostatics + distributed approximate drag; one-way coupling to Mantaflow',
             'integration_hz':fps*substeps,'quadrature_cells':cells**3,'drag_coefficient':drag_coefficient,
             'linear_damping_per_wet_volume_kg_m3_s':1000.,'angular_damping_factor':.45}
    return records,metrics


