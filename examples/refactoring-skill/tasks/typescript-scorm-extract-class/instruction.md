# Task: SCORM Again — Tame the God Class

## Context

You are working in `/app`, a TypeScript library (`scorm-again`) that implements the SCORM 2004 e-learning standard API. The project structure:

```
src/
  Scorm2004API.ts         # Main API class (~1000+ lines)
  cmi/
    scorm2004/
      Scorm2004CMI.ts     # CMI data model
      sequencing/         # Sequencing-related types
  ...
```

The `Scorm2004API` class in `src/Scorm2004API.ts` is the main entry point for the SCORM 2004 implementation. It handles API lifecycle (Initialize, Terminate, Commit), data model access (GetValue, SetValue), error handling, and sequencing/navigation logic — all in a single class.

## Requirement

The `Scorm2004API` class has grown into a God Class that handles too many responsibilities:

1. **API lifecycle management** (Initialize, Terminate, Commit)
2. **Data model access** (GetValue, SetValue with validation)
3. **Error handling and error codes**
4. **Sequencing and navigation** (adl.nav.request handling, sequencing rules)

The sequencing/navigation logic is particularly tangled with the rest of the API. Methods that handle `adl.nav.request` values, process sequencing rules, and manage navigation state are mixed in with basic data access methods.

Your task:
1. Extract the sequencing/navigation responsibility into its own class or module
2. The `Scorm2004API` class should delegate to the extracted class for all sequencing concerns
3. Keep the public API surface identical — external callers should not need to change

## Scope

- Focus on: `src/Scorm2004API.ts` and the sequencing-related code within it
- You may create new files in `src/` for extracted classes
- Do NOT modify: test files, build configuration, or the public API signatures
- Preserve: all existing behavior — Initialize, Terminate, GetValue, SetValue must work identically

## Quality Expectations

- Follow TypeScript idioms and the project's existing style
- Maintain type safety — no `any` types in the extracted code
- Keep the refactoring focused on sequencing extraction

## Success Criteria

1. `npm run build` succeeds (or equivalent build command)
2. All existing tests pass
3. `Scorm2004API.ts` is measurably smaller (at least 20% reduction in lines)
4. Sequencing logic lives in a separate class/module
5. Public API surface is unchanged
