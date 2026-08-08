# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Optional


class ConnectionString:
    """
    A type-safe "Connection String" representation that can parse/build constituent parts.
    """

    __server: Optional[str]
    __database: Optional[str]
    __user: Optional[str]
    __password: Optional[str]
    __provider: Optional[str]
    __connect_timeout: Optional[int]
    __command_timeout: Optional[int]

    def __init__(
        self,
        connection_str: Optional[str] = None
    ):
        self.__server = None
        self.__database = None
        self.__user = None
        self.__password = None
        self.__provider = None
        self.__connect_timeout = None
        self.__command_timeout = None
        if connection_str is not None:
            self.parse(connection_str)

    def __str__(self) -> str:
        parts = []
        if self.server is not None:
            parts.append(f'Server={self.server}')
        if self.database is not None:
            parts.append(f'Database={self.database}')
        if self.user is not None:
            parts.append(f'UID={self.user}')
        if self.password is not None:
            parts.append(f'PWD={self.password}')
        if self.provider is not None:
            parts.append(f'Provider={self.provider}')
        if self.connect_timeout is not None:
            parts.append(f'Connection Timeout={self.connect_timeout}')
        if self.command_timeout is not None:
            parts.append(f'Command Timeout={self.command_timeout}')
        return ';'.join(parts)

    @property
    def server(self) -> Optional[str]:
        return self.__server

    @server.setter
    def server(self, value: Optional[str]):
        self.__server = value

    @property
    def database(self) -> Optional[str]:
        return self.__database

    @database.setter
    def database(self, value: Optional[str]):
        self.__database = value

    @property
    def user(self) -> Optional[str]:
        return self.__user

    @user.setter
    def user(self, value: Optional[str]):
        self.__user = value

    @property
    def password(self) -> Optional[str]:
        return self.__password

    @password.setter
    def password(self, value: Optional[str]):
        self.__password = value

    @property
    def provider(self) -> Optional[str]:
        return self.__provider

    @provider.setter
    def provider(self, value: Optional[str]):
        self.__provider = value

    @property
    def connect_timeout(self) -> Optional[int]:
        return self.__connect_timeout

    @connect_timeout.setter
    def connect_timeout(self, value: Optional[int]):
        self.__connect_timeout = value

    @property
    def command_timeout(self) -> Optional[int]:
        return self.__command_timeout

    @command_timeout.setter
    def command_timeout(self, value: Optional[int]):
        self.__command_timeout = value

    def parse(self, connectionstring: Optional[str]) -> ConnectionString:
        parts = (
            []
            if connectionstring is None
            else connectionstring.split(';')
        )
        for part in parts:
            key, value = part.split('=')
            match key.lower():
                case 'server':
                    self.server = value
                case 'database':
                    self.database = value
                case 'uid' | 'user' | 'user id' | 'username':
                    self.user = value
                case 'pwd' | 'password' | 'pass':
                    self.password = value
                case 'provider':
                    self.provider = value
                case 'connection timeout':
                    self.connect_timeout = int(value)
                case 'command timeout':
                    self.command_timeout = int(value)
        return self


__all__ = ['ConnectionString']
