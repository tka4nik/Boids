import numpy as np
from numba import njit, prange, config

# config.DISABLE_JIT = False


def init_boids(boids: np.ndarray, asp: float, vrange: np.ndarray):
    n = boids.shape[0]
    random = np.random.default_rng()
    boids[:, 0] = random.uniform(0., asp, size=n)
    boids[:, 1] = random.uniform(0., 1., size=n)

    alpha = random.uniform(0, 2 * np.pi, size=n)
    velocity = random.uniform(*vrange, size=n)
    cos, sin = np.cos(alpha), np.sin(alpha)
    boids[:, 2], boids[:, 3] = velocity * cos, velocity * sin
    boids[:, 6] = random.integers(0, 2, size=n)

    # boids[0] = np.array([0.5, 0.5, 0, 0.5, 0, 0])
    # boids[1] = np.array([0.5, 0.55, 0, -0.1, 0, 0])
    # boids[2] = np.array([0.54, 0.525, -0.1, -0.1, 0, 0])
    # print(boids)


def directions(boids: np.ndarray, dt=float) -> np.ndarray:
    """

    :param boids:
    :param dt:
    :return: array N * (x0, y0, x1, y1) for Arrow
    """
    return np.hstack((
        boids[:, :2] - dt * boids[:, 2:4],
        boids[:, :2]
    ))


@njit
def njit_norm_axis1(vector: np.ndarray):
    norm = np.empty(vector.shape[0], dtype=np.float64)
    for j in prange(vector.shape[0]):
        norm[j] = np.sqrt(vector[j, 0] * vector[j, 0] + vector[j, 1] * vector[j, 1])
    return norm


@njit
def njit_norm_vector(vector: np.ndarray):
    norm = 0
    for j in range(vector.shape[0]):
        norm += vector[j] * vector[j]
    return np.sqrt(norm)


@njit
def distance(boids: np.ndarray, i: int):
    difference = boids[i, 0:2] - boids[:, 0:2]
    return njit_norm_axis1(difference)


@njit
def clip_array(array: np.ndarray, range: np.ndarray) -> np.ndarray:
    min_magnitude, max_magnitude = range
    norm = njit_norm_axis1(array)
    mask_max = norm > max_magnitude
    mask_min = norm < min_magnitude
    new_array = array.copy()
    if np.any(mask_max):
        new_array[mask_max] = (array[mask_max] / njit_norm_axis1(array[mask_max]).reshape(-1, 1)) * max_magnitude

    if np.any(mask_min):
        new_array[mask_min] = (array[mask_min] / njit_norm_axis1(array[mask_min]).reshape(-1, 1)) * min_magnitude

    return new_array


@njit
def clip_vector(vector: np.ndarray, range: np.ndarray) -> np.ndarray:
    min_magnitude, max_magnitude = range
    norm = njit_norm_vector(vector)
    mask_max = norm > max_magnitude
    mask_min = norm < min_magnitude
    new_vector = vector.copy()
    if mask_max:
        new_vector = (vector / norm) * max_magnitude

    if mask_min:
        new_vector = (vector / norm) * min_magnitude
    return new_vector


@njit
def separation(boids: np.ndarray, i: int, distance_mask: np.ndarray):
    distance_mask[i] = False
    directions = boids[i, :2] - boids[distance_mask][:, :2]
    directions *= (1 / (njit_norm_axis1(directions).reshape(-1, 1) + 0.0001))
    acceleration = np.sum(directions, axis=0)
    return acceleration - boids[i, 2:4]


@njit
def cohesion(boids: np.ndarray, i: int, distance_mask: np.ndarray):
    directions = boids[distance_mask][:, :2]
    acceleration = (np.sum(directions, axis=0) / directions.shape[0]) - boids[i, :2]
    # acceleration /= directions.shape[0]
    return acceleration - boids[i, 2:4]


@njit
def alignment(boids: np.ndarray, i: int, distance_mask: np.ndarray):
    velocity = boids[distance_mask][:, 2:4]
    acceleration = np.sum(velocity, axis=0)
    acceleration /= velocity.shape[0]
    return acceleration - boids[i, 2:4]


@njit
def compute_walls_interactions_bounce(boids: np.ndarray, i: int, aspect_ratio: float):
    mask_walls = np.empty(4)
    mask_walls[0] = boids[i, 1] > 1
    mask_walls[1] = boids[i, 0] > aspect_ratio
    mask_walls[2] = boids[i, 1] < 0
    mask_walls[3] = boids[i, 0] < 0

    if mask_walls[0]:
        boids[i, 3] = -boids[i, 3]
        boids[i, 1] = 1 - 0.001

    if mask_walls[1]:
        boids[i, 2] = -boids[i, 2]
        boids[i, 0] = aspect_ratio - 0.001

    if mask_walls[2]:
        boids[i, 3] = -boids[i, 3]
        boids[i, 1] = 0.001

    if mask_walls[3]:
        boids[i, 2] = -boids[i, 2]
        boids[i, 0] = 0.001


@njit
def walls(boids: np.ndarray, i: int, aspect_ratio: float):  # избегание стен - чем ближе к стене, тем больше значение ускорения от стены
    x = boids[i, 0]
    y = boids[i, 1]

    a_left = 1 / np.abs(x + 0.1)
    a_right = 1 / np.abs((x - aspect_ratio) + 0.01)

    a_bottom = 1 / (np.abs(y) + 0.1)
    a_top = 1 / (np.abs(y - 1.0) + 0.1)

    return np.array([a_left - a_right, a_bottom - a_top])


@njit
def compute_walls_interactions(boids: np.ndarray, i: int, aspect_ratio: float):
    mask_walls = np.empty(4)
    mask_walls[0] = boids[i, 1] > 1
    mask_walls[1] = boids[i, 0] > aspect_ratio
    mask_walls[2] = boids[i, 1] < 0
    mask_walls[3] = boids[i, 0] < 0

    if mask_walls[0]:
        boids[i, 1] = 0
    if mask_walls[1]:
        boids[i, 0] = 0
    if mask_walls[2]:
        boids[i, 1] = 1
    if mask_walls[3]:
        boids[i, 0] = aspect_ratio


@njit(parallel=True)
def flocking(boids: np.ndarray, perseption: float, coefficients: np.ndarray, aspect_ratio: float, v_range: np.ndarray,
             a_range: np.ndarray, wall_bounce: bool):
    for i in prange(boids.shape[0]):
        a_separation = np.zeros(2)
        a_cohesion = np.zeros(2)
        a_alignment = np.zeros(2)
        a_walls = np.zeros(2)

        # TODO: нечитаемый, но компактый говногод
        boid_class = int(boids[i, 6])
        class_coefficients = coefficients[boid_class * 2: (boid_class * 2) + 2]

        d = distance(boids, i)
        perception_mask = d < perseption

        # Макси расстояний
        separation_mask = d < perseption / 2
        separation_mask[i] = False
        cohesion_mask = np.logical_xor(perception_mask, separation_mask)
        alignment_mask = perception_mask
        alignment_mask[i] = False

        if wall_bounce:
            compute_walls_interactions_bounce(boids, i, aspect_ratio)
        else:
            compute_walls_interactions(boids, i, aspect_ratio)

        # Main interactions
        if np.any(perception_mask):
            for class_index in range(class_coefficients.shape[0]):
                # Маски классов
                class_mask = boids[:, 6] == class_index
                class_separation_mask = np.logical_and(separation_mask, class_mask)
                class_cohesion_mask = np.logical_and(cohesion_mask, class_mask)
                class_alignment_mask = np.logical_and(alignment_mask, class_mask)

                if np.any(class_separation_mask):
                    a_separation += class_coefficients[class_index, 0] * separation(boids, i, class_separation_mask)
                if np.any(class_cohesion_mask):
                    a_cohesion += class_coefficients[class_index, 1] * cohesion(boids, i, class_cohesion_mask)
                if np.any(class_alignment_mask):
                    a_alignment += class_coefficients[class_index, 2] * alignment(boids, i, class_alignment_mask)

                a_walls = walls(boids, i, aspect_ratio)

            a_separation = clip_vector(a_separation, a_range)
            a_cohesion = clip_vector(a_cohesion, a_range)
            a_alignment = clip_vector(a_alignment, a_range)
            a_walls = clip_vector(a_walls, a_range)

        acceleration = a_separation + a_cohesion + a_alignment + a_walls * class_coefficients[0, 3]
        boids[i, 4:6] = acceleration


def propagate(boids, delta_time, v_range):
    boids[:, 2:4] += boids[:, 4:6] * delta_time
    boids[:, 2:4] = clip_array(boids[:, 2:4], v_range)
    boids[:, 0:2] += boids[:, 2:4] * delta_time
