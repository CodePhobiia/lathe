import trimesh
import numpy as np

print('has_embree:', trimesh.ray.has_embree)
m = trimesh.creation.box(extents=(1, 1, 1))
print('default ray class:', type(m.ray).__module__, type(m.ray).__name__)

origins = np.array([[0.0, 0.0, 5.0]])
directions = np.array([[0.0, 0.0, -1.0]])
locs, idx, tri = m.ray.intersects_location(origins, directions, multiple_hits=False)
print('ray hit OK, locations:', locs)
