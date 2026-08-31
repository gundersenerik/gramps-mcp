# Merge semantics per field

What happens to each field when you call a `create_*` tool with a `handle`,
that is, when you update an existing record rather than create a new one.

## Provenance

**This table is derived from reading `src/gramps_mcp/client.py`, not from
testing against a live Gramps Web instance.** It describes what this MCP
server sends to the API. It does not describe what the API then does with
it. Rows marked "verify" are where those two could differ.

The suite is integration-only by design, so confirming this end to end needs
a Gramps Web instance that is safe to write to. There is no such instance
yet, and the production tree must not be used: it has no way to undo a bad
write.

## The rule

On `POST` (create, no `handle`) there is no merging. The payload is the
record.

On `PUT` (update, `handle` given) the client first `GET`s the existing
record, copies it, and then applies the payload field by field:

- A field whose name **ends in `_list`**, whose value **is a list**, and
  which **already exists on the record** is **concatenated** with what is
  there, de-duplicated:
  - entries that are mappings with a `ref` key are de-duplicated on `ref`
  - entries that are strings are de-duplicated by value
  - anything else is concatenated **with no de-duplication**
- Every other field is **replaced**.

Two consequences worth internalising:

- A field you do not send is left alone. This is why an update sending only
  name, gender and attributes preserved ten events and two family links.
- A field that does **not** exist on the record yet is replaced, not merged,
  even when its name ends in `_list`.

## Person

| Field | Behaviour | Notes |
| --- | --- | --- |
| `primary_name` | Replace | Whole object, including `surname_list` |
| `gender` | Replace | |
| `gramps_id`, `private`, `change` | Replace | |
| `alternate_names` | **Replace** | List-shaped but no `_list` suffix |
| `urls` | **Replace** | List-shaped but no `_list` suffix |
| `note_list` | Merge | De-duplicated by handle |
| `tag_list` | Merge | De-duplicated by handle |
| `family_list` | Merge | De-duplicated by handle |
| `parent_family_list` | Merge | De-duplicated by handle |
| `media_list` | Merge | De-duplicated on `ref` |
| `event_ref_list` | Merge | De-duplicated on `ref` |
| `attribute_list` | **Merge, no de-duplication** | See trap 2 |

## Family

| Field | Behaviour | Notes |
| --- | --- | --- |
| `father_handle`, `mother_handle` | Replace | |
| `urls` | **Replace** | No `_list` suffix |
| `child_handles` | **Never sent** | Converted to `child_ref_list` before the request |
| `child_ref_list` | Merge | De-duplicated on `ref` |
| `event_ref_list` | Merge | De-duplicated on `ref` |
| `note_list` | Merge | De-duplicated by handle |
| `media_list` | Merge | De-duplicated on `ref` |

## Event

| Field | Behaviour | Notes |
| --- | --- | --- |
| `type`, `date`, `description`, `place` | Replace | |
| `citation_list` | Merge | Sent as `[{"ref": handle}]`; verify |
| `note_list` | Merge | Sent as `[{"ref": handle}]`; verify |

Events are the one type whose list fields are rewritten on the way out, so
that handles reach the API in its reference shape. If the API returns these
as bare handle strings on `GET` rather than as reference mappings, the
existing and outgoing entries will not match each other and de-duplication
falls through to plain concatenation, which duplicates. **Verify against a
test tree before trusting repeated event updates.**

## Place

| Field | Behaviour | Notes |
| --- | --- | --- |
| `name`, `code`, `place_type`, `lat`, `long` | Replace | |
| `gramps_id`, `private` | Replace | |
| `alt_loc`, `alt_names`, `urls` | **Replace** | List-shaped but no `_list` suffix |
| `placeref_list` | Merge | |
| `citation_list`, `note_list`, `tag_list` | Merge | De-duplicated by handle |
| `media_list` | Merge | De-duplicated on `ref` |

## Source

| Field | Behaviour | Notes |
| --- | --- | --- |
| `title`, `author`, `pubinfo` | Replace | |
| `gramps_id`, `private`, `change` | Replace | |
| `reporef_list` | Merge | De-duplicated on `ref` |
| `note_list`, `tag_list` | Merge | De-duplicated by handle |
| `media_list` | Merge | De-duplicated on `ref` |
| `attribute_list` | **Merge, no de-duplication** | See trap 2 |

## Citation

| Field | Behaviour | Notes |
| --- | --- | --- |
| `date`, `page`, `source_handle` | Replace | |
| `gramps_id`, `private`, `change` | Replace | |
| `note_list`, `tag_list` | Merge | De-duplicated by handle |
| `media_list` | Merge | De-duplicated on `ref` |
| `attribute_list` | **Merge, no de-duplication** | See trap 2 |

## Note

| Field | Behaviour | Notes |
| --- | --- | --- |
| `text` | Replace | |
| `type` | Replace | |

A note has no list fields, so an update to a note is a straight overwrite of
whatever you send.

## Traps

**1. `urls` is replaced, not merged.** It carries a list but its name does
not end in `_list`, so the rule does not apply. Sending one URL on an update
discards every other URL on the record. The same holds for
`alternate_names`, `alt_names` and `alt_loc`.

**2. `attribute_list` accumulates duplicates.** Attribute entries are
mappings without a `ref` key, so neither de-duplication branch matches and
the lists are concatenated as-is. Writing the same attribute twice leaves it
on the record twice. Since attributes cannot currently be read back through
any tool, this accumulates unseen.

**3. A field absent from the record is replaced.** The merge branch requires
the key to already exist on the fetched record. The first time you set a
list field, it is written whole.

**4. `child_handles` is a convenience, not a field.** It is converted into
`child_ref_list` entries before the request and never sent under its own
name. Read it back as `child_ref_list`.

**5. Merging is client-side.** The client fetches, merges and sends the full
record. Two updates racing against the same record will lose one side's
changes; the last write wins.

## Still to confirm

- Whether the API returns `citation_list` and `note_list` on events as
  reference mappings or as bare handle strings. This decides whether event
  list merging de-duplicates or duplicates.
- Whether the API requires `_class` on `child_ref_list` entries. Both the
  fuller reference object and the `_class` discriminator are currently sent;
  the bundled `apispec.yaml` documents neither requirement.
- Whether attributes survive a round-trip at all, given they cannot be read
  back through any tool today.
