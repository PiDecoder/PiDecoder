# Mosaic layout

PiDecoder stores the video-wall layout in:

```text
/opt/pidecoder/config/layout.json
```

Use the **Disposition** tab in the Web administration interface to edit it.

## Grid size

The layout supports:

- 1 to 9 columns;
- 1 to 9 rows.

The current dimensions are controlled by:

```text
Colonnes
Lignes
```

Changing the grid size automatically attempts to repack the active cameras.

## Camera tiles

Each active camera receives a placement:

```json
{
  "camera": 0,
  "x": 0,
  "y": 0,
  "width": 2,
  "height": 2
}
```

Coordinates start at zero.

| Property | Meaning |
|---|---|
| `camera` | Active camera index |
| `x` | Column position |
| `y` | Row position |
| `width` | Tile width in grid cells |
| `height` | Tile height in grid cells |

## Move a camera

Drag a tile to another position.

PiDecoder attempts to:

1. place the selected camera at the requested position;
2. move other cameras to available cells;
3. reject the operation when the grid cannot contain the result.

Tiles can also be dropped onto another camera. PiDecoder swaps or repacks the affected positions when possible.

## Resize a camera

Available sizes:

```text
1×1
2×1
1×2
2×2
```

When the requested size does not fit, PiDecoder displays:

```text
Pas assez de place pour agrandir cette caméra
```

Increase the number of rows or columns, reduce another tile, or use a different template.

## Layout templates

### Uniform grid

```text
Grille uniforme
```

Places every active camera in a `1×1` tile.

### Main camera

```text
Caméra principale
```

Creates one large camera and places the remaining cameras around it.

The first active camera becomes the main camera.

### Two main cameras

```text
Deux principales
```

Creates two large views, followed by the remaining cameras.

### Free layout

```text
Libre
```

Keeps the current custom layout.

## Reset the order

```text
Réinitialiser l’ordre
```

Applies the uniform layout.

## Automatic layout saving

Layout changes are saved automatically after a short delay.

The interface displays:

```text
Disposition sauvegardée — clique sur Appliquer
```

Saving the layout does not restart the video wall. Click **Appliquer** to reload the running engine.

## Full screen at startup

Enable:

```text
Plein écran au démarrage
```

This stores:

```json
{
  "fullscreen_on_start": true
}
```

The exact display behavior depends on the native PiDecoder engine and active graphical session.

## Example layout

```json
{
  "columns": 3,
  "rows": 3,
  "fullscreen_on_start": false,
  "camera_order": [
    0,
    1,
    2,
    3
  ],
  "placements": [
    {
      "camera": 0,
      "x": 0,
      "y": 0,
      "width": 2,
      "height": 2
    },
    {
      "camera": 1,
      "x": 2,
      "y": 0,
      "width": 1,
      "height": 1
    },
    {
      "camera": 2,
      "x": 2,
      "y": 1,
      "width": 1,
      "height": 1
    },
    {
      "camera": 3,
      "x": 0,
      "y": 2,
      "width": 1,
      "height": 1
    }
  ]
}
```

## Normalization

PiDecoder normalizes layouts when they are loaded or saved.

It:

- limits rows and columns to the supported range;
- removes invalid camera indexes;
- removes duplicate placements;
- constrains tiles to the grid;
- attempts to resolve overlapping tiles;
- adds missing active cameras;
- preserves the active camera order when possible.

## Grid too small

When the configured grid cannot contain every active camera, the interface displays a warning.

Possible solutions:

- add rows;
- add columns;
- reduce large tiles;
- disable cameras that are not needed;
- apply the uniform template.

## Backups

Before replacing the layout through the Web configuration API, PiDecoder keeps:

```text
/opt/pidecoder/config/backups/layout.json.previous
```

Imports create timestamped `before-import` copies.

Installer upgrades also preserve the complete runtime backup directory.
