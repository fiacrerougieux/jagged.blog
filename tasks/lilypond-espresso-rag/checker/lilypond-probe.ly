%% Included before the score with -dinclude-settings. Writes one line per
%% note and per text marking to $PROBE_OUT, so a checker can read which hand
%% played what, on which staff, in which bar, and the words of each text
%% marking and dashed text line.
#(define probe-port (open-output-file (or (getenv "PROBE_OUT") "/dev/stdout")))
#(set-port-encoding! probe-port "UTF-8")
#(define probe-ids (make-hash-table))
#(define probe-next 0)
#(define (probe-id ctx)
   (or (hashq-ref probe-ids ctx #f)
       (begin (set! probe-next (1+ probe-next)) (hashq-set! probe-ids ctx probe-next) probe-next)))
#(define (probe-where context)
   (let* ((staff (ly:context-find context 'Staff))
          (score (ly:context-find context 'Score))
          (stem (assq-ref (ly:context-grob-definition context 'Stem) 'direction)))
     (format #f "~a\t~a\t~a\t~a\t~a\t~a\t~a"
       (probe-id context)
       (probe-id staff)
       (ly:context-id staff)
       (ly:context-property staff 'clefGlyph)
       (ly:context-property score 'currentBarNumber)
       (ly:moment-main (ly:context-property score 'measurePosition))
       (if (number? stem) stem "auto"))))
#(define (probe-mark context event)
   (let ((text (ly:event-property event 'text #f)))
     (if (markup? text)
         (format probe-port "mark\t~a\t~a\t~s\n"
           (probe-where context)
           (ly:moment-main (ly:context-current-moment context))
           (markup->string text)))))
#(define (Probe_engraver context)
   (make-engraver
     (listeners
       ((note-event engraver event)
         (let ((p (ly:event-property event 'pitch)))
           (if (ly:pitch? p)
               (format probe-port "note\t~a\t~a\t~a\n"
                 (probe-where context)
                 (ly:moment-main (ly:context-current-moment context))
                 (ly:pitch-semitones p)))))
       ((text-script-event engraver event)
         (format probe-port "text\t~a\t~a\t~s\n"
           (probe-where context)
           (ly:moment-main (ly:context-current-moment context))
           (markup->string (ly:event-property event 'text))))
       ;; Words over the music, like \mark \markup "L.H. crosses over".
       ((ad-hoc-mark-event engraver event) (probe-mark context event))
       ((text-mark-event engraver event) (probe-mark context event))
       ;; A dashed line with words at its start, like "L.H. over R.H. - - -|",
       ;; marks where it starts and where it stops.
       ((text-span-event engraver event)
         (let* ((start (eqv? (ly:event-property event 'span-direction) START))
                (bounds (assq-ref (ly:context-grob-definition context 'TextSpanner) 'bound-details))
                (left (and (pair? bounds) (assq-ref bounds 'left)))
                (text (and start (pair? left) (assq-ref left 'text))))
           (format probe-port "~a\t~a\t~a\t~s\n"
             (if start "span" "spanend")
             (probe-where context)
             (ly:moment-main (ly:context-current-moment context))
             (if (markup? text) (markup->string text) "")))))))
\layout { \context { \Voice \consists #Probe_engraver } }
