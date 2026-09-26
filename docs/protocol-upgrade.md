# Protocol Upgrade

# Protocol upgrade

The protocol is now version 3. It adds directed 64-bitsonarand echoes. Bots written for version
    2 still run without change, but they cannot use the new features.

## What changed

|  | Protocol 2 | Protocol 3 |
| Sending | SONAR <value>: one 32-bit value, in the facing direction | SONAR <N|E|S|W> <value>: up to four 64-bit values, one for each direction |
| Receiving | Only values up to 4294967295. Larger values are left out. | All values |
| Echoes | None | ECHOESline after the messages |

Both forms ofSONARwork at every version. The version only controls what the engine sends to your bot.

## Upgrading with a helper

Update the toolkit, then rununswbc updateon your bot folder. It replaces only the helper files with
    the ones the toolkit ships, and keeps each old helper as a.bakfile next to it. Your main file is not changed.

```
unswbc update my_bot
```

The new helper asks for protocol 3 inend_turn. Old sonar calls still work:send_sonar(message)(in C,unswbc_send_sonar(message)) still sends a 32-bit value in the
    facing direction. For the new features, usesend_sonar(direction, message)andget_sonar_echoes(in C,unswbc_send_sonar_toandunswbc_sonar_echoes).

Sonar messages are now 64-bit. If your code names the message type as 32-bit, for examplestd::vector<std::uint32_t>in C++ oruint32_t const *in C, change it tostd::uint64_toruint64_t, or useauto.

## Upgrading a bot without a helper

- PrintPROTOCOL 3beforeENDTURN. It applies from your next turn.
- Read sonar values as unsigned 64-bit integers.
- After the messages, read theECHOESline: five counts, in the order kelp, ally, ally head, enemy, enemy
        head.

```
SONAR E 1806
SONAR W 18446744073709551615
MOVE N
PROTOCOL 3
ENDTURN
```

On your next turn, the sonar part of the round block can look like this: one message from another dragon, and one
    echo each for kelp and an enemy head.

```
NUM_MSGS 1
90210
ECHOES 1 0 0 0 1
```

## Details

- A dragon made by a split keeps the protocol version of the dragon it split from.
- A dragon on protocol 2 never gets a value above 4294967295. The engine does not keep it for later.
- If you send a value above 4294967295, a bot on protocol 2 cannot receive it. Keep a value at 32 bits if an older
        bot must read it.
