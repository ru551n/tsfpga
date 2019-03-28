-- -----------------------------------------------------------------------------
-- Copyright (c) Lukas Vik. All rights reserved.
-- -----------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;


package types_pkg is

  type boolean_vec_t is array (integer range <>) of boolean;

  function to_sl(value : boolean) return std_logic;
  function to_bool(value : std_logic) return boolean;
  function to_int(value : boolean) return integer;
  function to_int(value : std_logic) return integer;

end package;

package body types_pkg is

  function to_sl(value : boolean) return std_logic is
  begin
    if value then
      return '1';
    end if;
    return '0';
  end function;

  function to_bool(value : std_logic) return boolean is
  begin
    if value = '1' then
      return true;
    elsif value = '0' then
      return false;
    end if;
    assert false report "Can not convert value " & to_string(value) severity failure;
    return false;
  end function;

  function to_int(value : boolean) return integer is
  begin
    if value then
      return 1;
    else
      return 0;
    end if;
  end function;

  function to_int(value : std_logic) return integer is
  begin
    if value = '1' then
      return 1;
    elsif value = '0' then
      return 0;
    end if;

    assert false report "Can not convert value " & to_string(value) severity failure;
    return 0;
  end function;

end package body;
