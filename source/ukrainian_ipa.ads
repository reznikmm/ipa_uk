--  SPDX-FileCopyrightText: 2026 Max Reznik <reznikmm@gmail.com>
--
--  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
------------------------------------------------------------------

--  IPA transcription of Ukrainian words, the same as ipa_uk.ipa
--  (https://github.com/lang-uk/ipa-uk) with check_accent => False.
--
--  The transcription is a pipeline of deterministic transducers generated
--  from the rewrite rules of ipa_uk.ipa (see generate_ada.py).

package Ukrainian_IPA is

   pragma Preelaborate;

   Maximum_Word_Length : constant := 64;
   --  The longest word accepted, in characters

   procedure Transcribe
     (Word    : Wide_Wide_String;
      Output  : out Wide_Wide_String;
      Last    : out Natural;
      Success : out Boolean);
   --  Writes the transcription of Word to Output (Output'First .. Last).
   --  Word may contain the letters of the Ukrainian alphabet in any case,
   --  apostrophes (' and ’), hyphens and stress marks (U+0301, U+0300)
   --  right after a vowel. Success is False when Word has anything else,
   --  is longer than Maximum_Word_Length, or the result does not fit into
   --  Output.

end Ukrainian_IPA;
