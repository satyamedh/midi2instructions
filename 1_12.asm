.device atmega328p

.equ DDRB = 4
.equ PORTB = 5

ldi r16,$30
out DDRB,r16

ldi r16,$20
rcall sendregisterstolaptop
out PORTB,r16



loop:
    rjmp loop


.include "rs232link.inc"