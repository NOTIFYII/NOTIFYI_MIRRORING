# Notifyi CAD scout: initial access and scope

Date: 2026-10-06. This is an initial handback, not a completed measured inventory or selected assembly.

## Authority and scope

Read omd-scout/SKILL.md fully and the installed pack's protocol/reference-assembly.md fully. User authorizes framing/scout artifacts under .omd only. Preserve tools/digital_twin production files, tests, existing changes, vanilla WebGL, assembly constraints, wiring, and camera controls. No hardware activity, remote modification, pushes, or approval claims.

Decisions requiring evidence: selection-to-transform access; axis translation; plane translation; axis rotation and precision input; locked-part explanation; desk grounding of actual transformed geometry at Y=0. Whole-app redesign and typography replacement are out of scope. Drag motion matters; decorative motion is irrelevant.

## Capability result

browser-rs is installed outside PATH at /Users/im_inwook/.local/share/oh-my-design/browser-rs/v0.1.10/browser-rs. Its --help succeeded. MCP initialize succeeded with protocol 2025-06-18, server version 0.1.10, tools capability. tools/list exposed browser_navigate, browser_snapshot, browser_evaluate, browser_drag, browser_take_screenshot and browser_close. These establish tool availability, not successful Chrome launch, CAD access, capture, or interaction measurement. No browser navigation or screenshot was completed in this initial handback. An isolated profile path under .omd was supplied to initialization; no existing browser profile was read.

Earlier lookup of a directory named 0.1.10 missed the actual v0.1.10 directory; that was a lookup error, not a missing provider. Direct Node import of packaged TypeScript failed with ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING; the binary's successful initialization supersedes that attempted helper import.

omd doctor passed Node, Playwright Chromium, .omd writable and pack prerequisites. It did not check browser-rs. Playwright was not used; protocol fallback conditions have not been established.

## Access evidence

User URL (first attempted remote source): https://cad.onshape.com/documents/9442f03bd8ccac084fda9dd3/w/039e8dbd53e0782540ea5b0d/e/6f08aa8ac3d3e5b3054f7782

Web read returned Internal Error. Cause unknown: do not label this a permission or login failure. This document's UI, geometry and transform behavior remain unobserved. Do not repeatedly retry a blocked source.

Official documented behavior, independently readable:

- https://cad.onshape.com/help/Content/PartStudio/transform.htm : Translate by XYZ offers arrow manipulation and numeric XYZ input; Rotate uses a selected axis and angle entry/graphic adjustment. This is Part Studio feature behavior, not proof of the user document's Assembly interaction.
- https://cad.onshape.com/help/Content/Home/triad_manipulator.htm : Assembly selection activates a triad; free drag, axis movement, plane movement, axis rotation, and contextual numeric positioning are documented. Fixed instances cannot drag; mated instances respect degrees of freedom. No pixel dimensions, timing or gesture performance were measured.
- https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-FFD25CD3-0707-429E-B0E6-B7F9984CDC4C.htm : Fusion supports manipulator plus numeric inputs, explicit coordinate spaces, pivot and point-to-position. Independent documentation family, not a captured UI brick.

## Source-inspected local behavior (not browser observation)

- workspace.js:14 defaults to assemblyTool=connect; 706-710 hides the gizmo unless assembly/place and unlocked.
- workspace.js:718-729 renders world-axis arrows or rotation rings, separately by transformMode; no plane handle in this function.
- workspace.css:105-109 declares 24px SVG interaction strokes, 4px visible translation core, 3px visible rotation core; these are source values, not measured rendered dimensions.
- workspace.js:787-812 selects on body pointerdown then starts camera drag except connected-joint interaction in motion mode. Free placement by dragging the body is not implemented there.
- index.html:21,28 puts move/rotate in inspector and numeric location in collapsed details. There is no selection-local toolbar in this inspected markup.
- workspace.js:121-122 constructs desk slab center Y=-0.25 with half-height 0.25, so its top is already exactly Y=0.
- workspace.js:268 uses mesh-centered position plus rotation and scale. Setting part.pos[1]=0 does not ground its lowest vertex.
- workspace.js:751 allows translation Y down to -12. No transformed-minimum-Y desk clamp appears in the inspected transform path.

## Protocol state

The first omd frame set attempt was rejected because the task-matrix argument was malformed; frame show reported no frame. No valid frame, measured fragment, candidate, selection, or user approval is claimed. Candidate assembly remains stopped until valid brief blocks and lawful measured component evidence exist.

Conclusion: measured research is potentially possible because browser-rs initialized, but not yet demonstrated. Remote CAD access is unresolved. Official-doc and local-source evidence can support a narrow scope immediately; it cannot substitute for measured visual capture or a passing candidate assembly.
