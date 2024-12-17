import React, { useContext, useState } from "react";
import { assets } from "../../assets/assets";
import { Context } from "../../context/Context";
import "./Sidebar.css";

const Sidebar = () => {
  const handleExtension = () => {
    setExtended((prevExtended) => {
      console.log("Toggling extended from", prevExtended, "to", !prevExtended);
      return !prevExtended;
    });
  };

  const [extended, setExtended] = useState(true);
  const { previousPrompt } = useContext(Context);

  return (
    <div className="sidebar">
      <div className="top">
        <img
          onClick={handleExtension}
          className="menu"
          src={assets.menu_icon}
          alt="menu_icon"
        />
        <div className="new-chat" >
          <img src={assets.plus_icon} alt="plus_icon" className="plus-icon" />
          {extended ? (
            <p>New Chat</p>
          ) : null}
        </div>
        <p className="recent-title">Recents</p>
        {extended ? (
          <div className="recent">
            {previousPrompt.map((item, index) => {
              return (
                <div className="recent-entry" key={index}>
                  <img src={assets.message_icon} alt="" />
                  <p className="">{item.length >15 ?item.slice(0, 20)+'...':item}</p>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
      <div className="bottom">
        {extended ? (
          <p className="sidebar-bottom-para-text">
            <a href="https://www.genaiprotos.com/"><img src={assets.genAILogo} alt="" width={150} /></a>
          </p>
        ) : null}
      </div>
    </div>
  );
};

export default Sidebar;
