import time
from mido import MidiFile
import numpy as np
import sounddevice as sd

mid = MidiFile('tetris_edited.mid')

for i, track in enumerate(mid.tracks):
    print('Track {}: {}'.format(i, track.name))
    for msg in track:
        print(msg)


def get_freq_from_midi_note(midi_note: int) -> int:
    # 69 -- A4 -- 440Hz -- Base definition for midi
    base_note = 69
    base_frequency = 440
    # every increment/decrement is 1 semitone
    distance_from_a4 = (midi_note - base_note)
    # each octave(12 semitones) doubles frequency
    # Thus, each seminote changes the frequency by 2^(1/12)
    multiplier = 2 ** (distance_from_a4 / 12)
    # For a simple life, will round the frequency (also arduino has no FPU :(( )
    return round(multiplier * base_frequency)

def get_duration_ms_from_ticks(ticks: int, tempo: int, ticks_per_beat: int) -> int:
    # tempo is in microseconds per beat
    # ticks_per_beat is the number of ticks per beat
    return round(ticks * tempo / ticks_per_beat / 1000)

# stolen from online I aint writing ts, only for testing anyways
def play_frequency(frequency, duration_ms):
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)

    t = np.arange(num_samples) / sample_rate
    wave = np.sin(2 * np.pi * frequency * t)

    audio = wave.astype(np.float32)

    sd.play(audio, samplerate=sample_rate)
    sd.wait()

def get_timer1_ticks_from_hz(freq: int, CPU_F: int) -> int:
    ocr = int((CPU_F / (2 * freq)) - 1)
    if ocr > 0xffff:
        raise ValueError(f"Frequency {freq} is too low for CPU frequency {CPU_F}'s default prescalar bits. OCR value exceeds 16-bit limit!!")
    return ocr

class TrackEvent:
    def __init__(self, note: int, time: int):
        self.note = note # -1 is no note, 0-127 are valid midi notes
        self.time = time # absolute time in ticks


    def __str__(self):
        if self.note == -1:
            return f"Wait {self.time} ticks"
        else:
            return f"Play {self.note} for {self.time} ticks"

events = []
tempo = 0 # in us/beat
current_note = -1
current_note_start = -1
current_tick = 0
last_event_tick = 0 # will use these to calculate deltas

ticks_per_beat = mid.ticks_per_beat

set = False
# extract events from the piano track
for i, track in enumerate(mid.tracks):
    print('Track {}: {}'.format(i, track.name))
    if track.name == "Piano" or track.name == "Piano, Piano":
        # dump to [events] for parsing
        for msg in track:
            current_tick += msg.time
            if msg.is_meta and msg.type == 'set_tempo':
                print(f"Tempo: {msg.tempo} microseconds per beat")
                tempo = msg.tempo
            elif msg.type == 'note_on':
                if msg.velocity > 0:
                    # note on
                    current_note = msg.note
                    current_note_start = current_tick
                else:
                    # note off
                    duration = current_tick - current_note_start
                    gap = current_note_start - last_event_tick

                    if gap > 0:
                        events.append(TrackEvent(-1, gap)) # wait event
                    events.append(TrackEvent(current_note, duration)) # note event

                    last_event_tick = current_tick
                    current_note = -1
        break # don't need to parse other tracks



print([str(event) for event in events])

# convert events to frequencies and durations in ms

class NormalizedEvent:
    def __init__(self, frequency: int, duration_ms: int):
        self.frequency = frequency # 0 is wait, >0 is frequency in Hz
        self.duration_ms = duration_ms # duration in milliseconds

    def __str__(self):
        if self.frequency == 0:
            return f"Wait {self.duration_ms} ms"
        else:
            return f"Play {self.frequency} Hz for {self.duration_ms} ms"

normalized_events = []
for event in events:
    if event.note == -1:
        # wait event
        frequency = 0
    else:
        frequency = get_freq_from_midi_note(event.note)
    duration_ms = get_duration_ms_from_ticks(event.time, tempo, ticks_per_beat)
    normalized_events.append(NormalizedEvent(frequency, duration_ms))

print([str(event) for event in normalized_events])

# # test play the events
# for event in normalized_events:
#     if event.frequency == 0:
#         # wait
#         time.sleep(event.duration_ms / 1000)
#     else:
#         play_frequency(event.frequency, event.duration_ms)

# WORKS YAY


# export to some format for arduino to read
# each event can be boiled down to 32 bits, 16 bits for frequency, 16 bits for duration in ms, all appended to a single array
# parser can read one event at a time, thus no need for delimiters or headers blah blah
# two modes of export, C++ array or just raw hex
EXPORT_MODE = "C++" #  "BIN" or "C++" or "ASM" or "ASM_T1T"

# First, convert to an array of 32-bit integers, one entry for each event
export_data = []
for event in normalized_events:
    # Combine frequency and duration into a single 32-bit integer
    combined = (event.frequency << 16) | (event.duration_ms & 0xFFFF)
    export_data.append(combined)

if EXPORT_MODE == "C++":
    # Export as a C++ array
    with open("exported_data.cpp", "w") as f:
        f.write("const uint32_t midi_events[] = {\n")
        for data in export_data:
            f.write(f"    0x{data:08X},\n")
        f.write("};\n")

elif EXPORT_MODE == "BIN":
    # lowk just print it as one continuous hex string, which can be pasted in the assembly code later
    data_string = "".join(f"{data:08X}" for data in export_data)
    print(data_string)

elif EXPORT_MODE == "ASM":
    # Export as assembly .word directives
    with open("exported_data.asm", "w") as f:
        f.write("midi_events:\n")
        for data in export_data:
            frequency = (data >> 16) & 0xFFFF
            duration = data & 0xFFFF
            f.write(f"    .dw ${frequency:04X}, ${duration:04X}\n")
        f.write("midi_events_end:\n")

elif EXPORT_MODE == "ASM_T1T":
    # Export as assembly .word directives but with T1 ticks instead of freq
    with open("exported_data_t1t.asm", "w") as f:
        f.write("midi_events:\n")
        for data in export_data:
            frequency = (data >> 16) & 0xFFFF
            t1_ticks = get_timer1_ticks_from_hz(frequency, CPU_F=16000000) if frequency > 0 else 0
            duration = data & 0xFFFF
            f.write(f"    .dw ${t1_ticks:04X}, ${duration:04X}\n")
        f.write("midi_events_end:\n")






