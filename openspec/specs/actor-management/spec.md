## ADDED Requirements

### Requirement: List actors in the current level
The server SHALL expose a `list_actors` tool that returns all actors present in the currently open level, with their labels, classes, and transforms.

#### Scenario: Level has actors
- **WHEN** `list_actors` is called with an open level containing actors
- **THEN** it SHALL return `{"ok": true, "actors": [{"label": "...", "class": "...", "location": [...], "rotation": [...], "scale": [...]}, ...]}`

#### Scenario: Empty level
- **WHEN** `list_actors` is called on a level with no actors
- **THEN** it SHALL return `{"ok": true, "actors": []}`

### Requirement: Get actor properties
The server SHALL expose a `get_actor_properties` tool that returns the properties of a named actor, including all component properties, as a nested JSON dict.

#### Scenario: Actor found by label
- **WHEN** `get_actor_properties` is called with a valid actor label
- **THEN** it SHALL return `{"ok": true, "properties": {...}}` containing the actor's editable properties

#### Scenario: Actor not found
- **WHEN** `get_actor_properties` is called with a label that matches no actor in the level
- **THEN** it SHALL return `{"ok": false, "error": "Actor '<label>' not found in the current level"}`

### Requirement: Place an actor
The server SHALL expose a `place_actor` tool that spawns an actor of a given class at a specified location, rotation, and scale.

#### Scenario: Valid class placed at location
- **WHEN** `place_actor` is called with a valid UE class path and transform values
- **THEN** a new actor SHALL be spawned in the level and the tool SHALL return `{"ok": true, "label": "<assigned label>", "name": "<object name>"}`

#### Scenario: Invalid class path
- **WHEN** `place_actor` is called with a class path that cannot be resolved
- **THEN** it SHALL return `{"ok": false, "error": "Class '<path>' not found"}`

### Requirement: Delete an actor
The server SHALL expose a `delete_actor` tool that removes an actor from the current level by its label.

#### Scenario: Actor deleted successfully
- **WHEN** `delete_actor` is called with a valid actor label
- **THEN** the actor SHALL be removed from the level and the tool SHALL return `{"ok": true}`

#### Scenario: Actor not found for deletion
- **WHEN** `delete_actor` is called with a label that matches no actor
- **THEN** it SHALL return `{"ok": false, "error": "Actor '<label>' not found"}`

### Requirement: Set actor transform
The server SHALL expose a `set_actor_transform` tool that sets the world-space location, rotation, and/or scale of a named actor. Any of the three components MAY be omitted to leave it unchanged.

#### Scenario: Full transform set
- **WHEN** `set_actor_transform` is called with location, rotation, and scale
- **THEN** the actor's world transform SHALL be updated and the tool SHALL return `{"ok": true}`

#### Scenario: Partial transform update
- **WHEN** `set_actor_transform` is called with only location provided
- **THEN** only the actor's location SHALL change; rotation and scale SHALL remain unchanged

### Requirement: Set actor property
The server SHALL expose a `set_actor_property` tool that sets a named property on an actor or one of its components to a given value.

#### Scenario: Property set on actor
- **WHEN** `set_actor_property` is called with a valid actor label, property path, and value
- **THEN** the property SHALL be updated and the tool SHALL return `{"ok": true}`

#### Scenario: Invalid property path
- **WHEN** `set_actor_property` is called with a property path that does not exist on the actor
- **THEN** it SHALL return `{"ok": false, "error": "Property '<path>' not found on actor '<label>'"}`
