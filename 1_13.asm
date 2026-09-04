.device atmega328p

.equ DDRB = 4
.equ PORTB = 5

ldi r16,$30
out DDRB,r16

.def YL = r28
.def YH = r29

loop:
    rcall led_on
    ; load 500(0x1f4) into Y
    ldi YL, 0xF4
    ldi YH, 0x01
    rcall wait_duration
    rcall led_off
    ; wait again
    ldi YL, 0xF4
    ldi YH, 0x01
    rcall wait_duration
    rjmp loop

led_on:
    ; turn on LED
    ldi r16, $20
    out PORTB, r16
    ret

led_off:
    ; turn off LED
    ldi r16, $00
    out PORTB, r16
    ret

wait_1ms:
    ; 4-cycle loop, 16000 cycles, therefore 16000/4 = 4000 iterations, 0x0FA0
    ldi r21, 0xA0
    ldi r22, 0x0F

wait_1ms_loop:
    subi r21, 1
    sbci r22, 0
    brne wait_1ms_loop
    ret

wait_duration:
    ; wait for duration in Y
    ; first copy Y to our own registers so we dont modify Y
    mov r19, YL
    mov r20, YH

wait_duration_loop:
    ; wait 1ms
    rcall wait_1ms

    subi r19, 1
    sbci r20, 0
    brne wait_duration_loop
    ret
