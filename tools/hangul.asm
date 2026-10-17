; 론머맨 한글 패치 - 문자열 렌더러/메시지 후킹
lorom
incsrc "gen.asm"        ; !MsgSize, !MsgSrc, !MsgBank (빌더 생성)

; ---------------------------------------------------------------
; 문자열 렌더러 $9F:9D4D (X = 뱅크 $85 문자열 주소)
org $9F9D4D
    jml TextHook

org $8187E8             ; 메시지 출력: and #$3FFF / tax
    jsl MsgStart

org $818825             ; 메시지 글자 -> 타일 번호
    jsl MsgTile
    nop #3

org $9FE000
TextHook:
    lda.l $850000,x
    and #$00FF
    cmp #$00FE
    beq .kor
    cmp #$00FD
    beq .var
    sta $85                 ; 원본 처리
    inx
    lda #$0280
    sta $83
    jml $9F9D5C
.var:
    lda $5C07               ; 0 = 플레이어 1
    beq .kor
    inx #3
.kor:
    lda $8D                 ; DP 임시 영역 보존
    pha
    lda $8F
    pha
    lda.l $850001,x
    sta $8D
    lda.l $850002,x
    sta $8E
    ; 머리: 속도(1) 타일바이트수(2) 타일주소(3)
    ldy #$0000
    lda [$8D],y
    and #$00FF
    sta $85
    ldy #$0001
    lda [$8D],y
    beq .nodma
    sta $23AA
    ldy #$0003
    lda [$8D],y
    sta $20A4
    ldy #$0005
    lda [$8D],y
    and #$00FF
    sta $21A6
    lda #$6008              ; BG3 글자 타일 1번부터
    sta $22A8
    lda #$0080
    sta $24AC
    jsl $8181B1
.nodma:
    lda #$0280
    sta $83
    ldy #$0006
.loop:
    lda [$8D],y
    and #$00FF
    iny
    cmp #$00FF
    bne +
    jmp .end
+   cmp #$0080
    bne +
    jmp .pos
+   cmp #$0084
    beq .kchar
    cmp #$0020
    beq .space
    clc
    adc #$0089
    bra .put
.kchar:
    lda [$8D],y
    and #$00FF
    iny
    bra .put
.space:
    lda #$0000
.put:
    ora #$3000
    ldx $83
    sta.l $7F0000,x
    inc $83
    inc $83
    cmp #$3000
    beq .loop
    ldx $85
    bne .loop
    ; 타자기 효과: 타일맵 전송 후 5프레임 대기 (원본과 동일)
    phy
    lda #$007F
    sta $21A6
    lda #$0000
    sta $20A4
    lda #$7800
    sta $22A8
    lda #$0800
    sta $23AA
    lda #$0080
    sta $24AC
    jsl $8181B1
    lda #$0004
    sta $63
.wait:
    jsl $8181A7
    jsl $81FCE3
    lda $5D2B
    ora $5D2D
    beq +
    inc $85
+   jsl $868000
    dec $63
    bpl .wait
    ply
    jmp .loop
.pos:
    lda [$8D],y
    and #$00FF
    sta $2F36
    iny
    lda [$8D],y
    and #$00FF
    iny
    asl #5
    ora $2F36
    asl
    sta $83
    jmp .loop
.end:
    pla
    sta $8F
    pla
    sta $8D
    jml $9F9E29

; ---------------------------------------------------------------
MsgStart:
    and #$3FFF
    tax
    lda $69
    bne .r
    lda.l !MsgSize,x
    beq .r
    sta $23AA
    lda.l !MsgSrc,x
    sta $20A4
    lda.w #!MsgBank
    sta $21A6
    lda #$6300              ; 타일 $60부터
    sta $22A8
    lda #$0080
    sta $24AC
    phx
    jsl $8181B1
    plx
.r:
    rtl

MsgTile:
    cmp #$0020
    bcs .asc
    clc
    adc #$005F
    bra .o
.asc:
    clc
    adc #$015F
.o:
    ora $2F38
    rtl
