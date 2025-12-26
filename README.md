# Pool

This is a physics based single player 2D pool simulator built in Python, using Pygame and Pymunk. It has togglable stage hazards that affect the gameplay. These hazards move around the stage every round. 

##### Prerequisites 

This program was built in Python 3.13.
`pip install pygame pymunk`

##### Controls 

- There are two modes: Aim and Power
- The mouse is used to aim the cueball during Aiming Mode
- During Power Mode, the aim is locked and the power is adjusted using the right sidebar.
- To shoot the ball, release the sidebar at any point (Release at the top to cancel)
- Press `k` to speed up the game
- Press `r` to go back to the main menu

##### Features

- Hazards are togglable in the main menu.
- High Score COunter: Balls are worth a cetain amount of points
   - Solids and Stripes are worth `100` points
   - The black 8 ball is worth `500` points
   - The cueball detucts `50` points if potted
- Golden Pocket: Every turn, a pocket is randomly chosen as a golden pocket. Potting a ball there results in double the points

##### Hazards
- Zones: These are areas that slow (mud zones) or speed up (ice zones) dramatically
- Portals: Entering a portal with any ball with teleport it to the other portal
- Bumpers: Static obstacles that provide high rebound potential for any balls that collide with it.
